"""TennisService: player resolution, Asia/Macau time scopes, cache policy.

The service is the single source of truth for REST and chat tools. It never
exposes provider DTOs, and time semantics live here as tested service rules
rather than prompt instructions.
"""

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from app.cache import AsyncTTLCache, CacheOutcome
from app.domain import (
    CapabilityStatus,
    CircuitTier,
    Discipline,
    Gender,
    HeadToHead,
    Match,
    MatchSnapshot,
    MatchStatus,
    Player,
)
from app.errors import AppError
from app.intelligence import IntelligencePacket, IntelligenceTopic, build_intelligence_packet
from app.markets.quotes import (
    best_levels,
    display_quote,
    outcome_levels,
    QuoteState,
)
from app.players.models import (
    PlayerAliasKind,
    PlayerCandidate,
    PlayerProfileData,
    PlayerProfileView,
    PlayerResolution,
    PlayerResolutionStatus,
    PlayerResultPage,
    PlayerSeasonRecord,
    RankingPage,
    ResultOutcome,
    Tour,
)
from app.providers.base import TennisDataProvider
from app.realtime.reducer import normalize_snapshot_quality, reduce_live_snapshot

UNPROMOTED_REASONS = frozenset(
    {"MODEL_UNPROMOTED", "PROMOTION_NOT_GRANTED", "ARTIFACT_INVALID"}
)
MAIN_TOUR_TIERS = frozenset({"atp", "wta"})


def p3_model_availability(*, tier, prediction, observation) -> str:
    """Explicit model availability for one market row (spec §6.1).

    Never inferred from a null action: `out_of_scope` marks levels the model
    deliberately does not cover, `not_evaluated` means no evidence exists
    yet, `eligible_unpromoted` means the market is in domain but the model is
    not promoted, and `available` requires real prediction evidence.
    """
    if tier is None:
        return "not_evaluated"  # no active link: nothing was evaluated
    if tier not in MAIN_TOUR_TIERS:
        return "out_of_scope"  # deliberately outside the model domain
    if prediction is not None:
        if prediction.availability.value in ("available", "degraded"):
            return "available"
        if prediction.availability.value in ("unpromoted", "unavailable"):
            return "eligible_unpromoted"
    if observation is not None and (observation.reason_code or "") in UNPROMOTED_REASONS:
        return "eligible_unpromoted"
    return "not_evaluated"


class MatchTimeScope(StrEnum):
    TODAY = "today"
    TONIGHT = "tonight"
    NEXT = "next"


CIRCUIT_PRIORITY = {
    CircuitTier.ATP: 0,
    CircuitTier.WTA: 0,
    CircuitTier.CHALLENGER: 1,
    CircuitTier.ITF: 2,
    CircuitTier.OTHER: 3,
}


class MatchFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    circuits: tuple[CircuitTier, ...] = (CircuitTier.ATP, CircuitTier.WTA)
    genders: tuple[Gender, ...] = ()  # empty = all genders
    disciplines: tuple[Discipline, ...] = (Discipline.SINGLES,)

    @classmethod
    def default(cls) -> "MatchFilters":
        return cls()


class FacetCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    circuits: dict[CircuitTier, int]
    genders: dict[Gender, int]
    disciplines: dict[Discipline, int]


class MatchCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    matches: tuple[Match, ...]
    filters: MatchFilters
    facet_counts: FacetCounts
    featured_match_id: str | None


class PlayerResultsScope(StrEnum):
    YESTERDAY = "yesterday"
    LAST = "last"
    RECENT = "recent"


class PlayerResults(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    scope: PlayerResultsScope
    availability: CapabilityStatus
    matches: tuple[Match, ...]


class HeadToHeadResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    first_player_id: str
    second_player_id: str
    availability: CapabilityStatus
    head_to_head: HeadToHead | None


HISTORY_FETCH_LIMIT = 10
HISTORY_FRESH_TTL = 600
HISTORY_EMPTY_TTL = 60


class _UnsupportedCapability:
    """Sentinel: provider answered typed `unsupported` (negative-cached)."""


_UNSUPPORTED = _UnsupportedCapability()


def catalog_sort_key(match: Match) -> tuple[int, int, datetime, str]:
    return (
        CIRCUIT_PRIORITY[match.tournament.circuit],
        0 if match.status is MatchStatus.LIVE else 1,
        match.scheduled_at or datetime.max.replace(tzinfo=timezone.utc),
        match.id,
    )


def _is_composite_player_name(name: str) -> bool:
    normalized = name.casefold()
    return "/" in normalized or "&" in normalized or " vs " in normalized


# Canonical catalog status mapping for local-`api`-role list reads.
_CATALOG_STATUS = {"live": MatchStatus.LIVE, "upcoming": MatchStatus.SCHEDULED}


def _status_for(status: str) -> MatchStatus:
    return _CATALOG_STATUS[status]


def _player_preference_key(player: Player) -> tuple[bool, int]:
    return (player.ranking is None, player.ranking if player.ranking is not None else 1_000_000)


def tonight_window(now_local: datetime) -> tuple[datetime, datetime]:
    day = now_local.date()
    if now_local.time() < time(6):
        start_day = day - timedelta(days=1)
    else:
        start_day = day
    start = datetime.combine(start_day, time(18), tzinfo=now_local.tzinfo)
    return start, start + timedelta(hours=12)


class TennisService:
    def __init__(
        self,
        provider: TennisDataProvider,
        cache: AsyncTTLCache[str, object],
        now: Callable[[], datetime],
        timezone: str,
        *,
        snapshots=None,
        publisher=None,
        resolver=None,
        directory=None,
        seeder=None,
        catalog=None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._now = now
        self._timezone = ZoneInfo(timezone)
        self._snapshots = snapshots
        self._publisher = publisher
        self._resolver = resolver
        self._directory = directory
        self._seeder = seeder
        self._seeded = seeder is None
        # Canonical match catalog (local `api` role only). When supplied,
        # ordinary list reads come from the persisted catalog first; when
        # None every path below is unchanged.
        self._catalog = catalog

    async def _ensure_seeded(self) -> None:
        if not self._seeded:
            self._seeded = True
            await self._seeder()

    async def resolve_player(
        self,
        query: str,
        *,
        context_player_ids: tuple[str, ...] = (),
        limit: int = 5,
    ):
        """Shared deterministic resolution; legacy fallback only when no
        resolver is injected (livetennis/replay unit contracts)."""
        if self._resolver is not None:
            return await self._resolver.resolve(
                query, context_player_ids=context_player_ids, limit=limit
            )
        players = await self.search_players(query)
        individuals = [
            player for player in players if not _is_composite_player_name(player.name)
        ]
        unique: dict[str, Player] = {}
        for player in individuals:
            key = player.name.strip().casefold()
            current = unique.get(key)
            if current is None or _player_preference_key(player) < _player_preference_key(current):
                unique[key] = player
        normalized_players = list(unique.values())
        exact = [
            player
            for player in normalized_players
            if player.name.strip().casefold() == query.strip().casefold()
        ]
        selected = exact or normalized_players
        candidates = tuple(
            PlayerCandidate(
                player=player,
                matched_alias=player.name,
                alias_kind=PlayerAliasKind.FULL,
                current_rank=player.ranking,
            )
            for player in selected
        )
        if len(candidates) == 1:
            return PlayerResolution(
                status=PlayerResolutionStatus.RESOLVED,
                query=query,
                player=candidates[0].player,
                candidates=candidates,
            )
        if not candidates:
            return PlayerResolution(
                status=PlayerResolutionStatus.NOT_FOUND, query=query
            )
        return PlayerResolution(
            status=PlayerResolutionStatus.AMBIGUOUS, query=query, candidates=candidates
        )

    async def search_players(self, query: str) -> list[Player]:
        normalized = query.strip()
        if not normalized:
            raise AppError("invalid_request", "Player query is required", 422)

        async def load() -> object:
            return await self._provider.search_players(normalized)

        outcome = await self._cache.get_or_load(
            f"players:{normalized.casefold()}",
            load,
            ttl=lambda value: 30 if not cast(list[Player], value) else 3600,
            stale_ttl=0,
        )
        return cast(list[Player], outcome.value)

    async def get_rankings_page(
        self,
        tour: Tour,
        *,
        page: int,
        page_size: int,
        country_code: str | None,
    ) -> RankingPage:
        if self._directory is None:
            raise AppError("unsupported", "Rankings require the player directory", 501)
        await self._ensure_seeded()
        entries, total = await self._directory.get_rankings(
            tour, page=page, page_size=page_size, country_code=country_code
        )
        _, tour_total = await self._directory.get_rankings(
            tour, page=1, page_size=1, country_code=None
        )
        as_of = max((entry.fetched_at for entry in entries), default=self._now())
        return RankingPage(
            tour=tour,
            page=page,
            page_size=page_size,
            total=total,
            entries=entries,
            as_of=as_of,
            availability=CapabilityStatus.AVAILABLE
            if tour_total
            else CapabilityStatus.UNAVAILABLE,
        )

    async def get_player_profile_view(
        self, player_id: str, *, season: int | None = None
    ) -> PlayerProfileView:
        await self._ensure_seeded()
        current_year = self._now().year
        selected = season if season is not None else current_year
        if not current_year - 4 <= selected <= current_year:
            raise AppError("invalid_request", "Season outside the five-season window", 422)
        directory_player = None
        if self._directory is not None:
            directory_player = await self._directory.get_player(player_id)
            if directory_player is None:
                raise AppError("not_found", "Player not found", 404)
        profile = await self._load_profile(player_id)
        # The product window is the current season plus the four prior ones;
        # supplier payloads can carry longer histories, and the view never
        # exposes seasons outside the selectable window.
        windowed = tuple(
            record
            for record in profile.seasons
            if current_year - 4 <= record.season <= current_year
        )
        if len(windowed) != len(profile.seasons):
            profile = profile.model_copy(update={"seasons": windowed})
        season_record = next(
            (record for record in profile.seasons if record.season == selected), None
        )
        current_match: Match | None = None
        live = await self._list_by_player_id("live", player_id)
        if live:
            current_match = live[0]
        else:
            upcoming = await self._list_by_player_id("upcoming", player_id)
            if upcoming:
                current_match = upcoming[0]
        return PlayerProfileView(
            profile=profile,
            selected_season=selected,
            season_record=season_record,
            current_match=current_match,
        )

    async def _load_profile(self, player_id: str) -> PlayerProfileData:
        async def load() -> object:
            try:
                return await self._provider.get_player_profile(player_id)
            except AppError as error:
                if error.code == "not_found":
                    return _UNSUPPORTED
                raise

        outcome = await self._cache.get_or_load(
            f"profile:{player_id}",
            load,
            ttl=lambda value: 60 if value is _UNSUPPORTED else 3600,
            stale_ttl=0,
        )
        if outcome.value is _UNSUPPORTED:
            raise AppError("not_found", "Player not found", 404)
        return cast(PlayerProfileData, outcome.value)

    async def get_player_result_page(
        self,
        player_id: str,
        *,
        season: int,
        tiers: tuple[CircuitTier, ...],
        outcome: ResultOutcome,
        page: int,
    ) -> PlayerResultPage:
        await self._ensure_seeded()
        current_year = self._now().year
        if not current_year - 4 <= season <= current_year:
            raise AppError("invalid_request", "Season outside the five-season window", 422)
        player: Player | None = None
        if self._directory is not None:
            directory_player = await self._directory.get_player(player_id)
            if directory_player is None:
                raise AppError("not_found", "Player not found", 404)
            player = directory_player.player
        raw = await self._load_season_results(player_id, season)
        filtered = [
            match
            for match in raw
            if (not tiers or match.tournament.circuit in tiers)
            and (
                outcome is ResultOutcome.ALL
                or (outcome is ResultOutcome.WON) == (match.winner_player_id == player_id)
            )
        ]
        filtered.sort(
            key=lambda match: match.scheduled_at
            or datetime.max.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        page_size = 20
        start = (max(1, page) - 1) * page_size
        if player is None:
            player = raw[0].players[0] if raw else Player(id=player_id, name="Unknown player")
        return PlayerResultPage(
            player=player,
            season=season,
            tiers=tiers,
            outcome=outcome,
            page=page,
            page_size=page_size,
            total=len(filtered),
            matches=tuple(filtered[start : start + page_size]),
            availability=CapabilityStatus.AVAILABLE
            if raw
            else CapabilityStatus.UNAVAILABLE,
        )

    async def _load_season_results(self, player_id: str, season: int) -> tuple[Match, ...]:
        async def load() -> object:
            try:
                return await self._provider.get_player_results_for_period(
                    player_id, start=date(season, 1, 1), end=date(season, 12, 31)
                )
            except AppError as error:
                if error.code == "not_found":
                    return _UNSUPPORTED
                raise

        outcome = await self._cache.get_or_load(
            f"results:{player_id}:{season}",
            load,
            ttl=lambda value: 60 if value is _UNSUPPORTED or not value else 600,
            stale_ttl=0,
        )
        if outcome.value is _UNSUPPORTED:
            raise AppError("not_found", "Player not found", 404)
        return cast(tuple[Match, ...], outcome.value)

    async def get_latest_player_results(
        self, player_id: str, *, limit: int
    ) -> tuple[Match, ...]:
        """Result-count semantics for `last`/`recent` across the five-season window.

        Seasons are queried newest first through the cached on-demand season
        path and loading stops as soon as enough finished matches are known;
        the fixed 30-day recent fetch never implements this scope.
        """
        if not 1 <= limit <= 10:
            raise AppError("invalid_request", "Limit must be between 1 and 10", 422)
        await self._ensure_seeded()
        current_year = self._now().astimezone(self._timezone).year
        collected: dict[str, Match] = {}
        for season in range(current_year, current_year - 5, -1):
            raw = await self._load_season_results(player_id, season)
            for match in raw:
                if match.status is not MatchStatus.FINISHED:
                    continue
                if match.scheduled_at is None:
                    continue
                collected.setdefault(match.id, match)
            if len(collected) >= limit:
                break
        ordered = sorted(
            collected.values(),
            key=lambda match: (match.scheduled_at, match.id),
            reverse=True,
        )
        return tuple(ordered[:limit])

    async def get_player_season_record(
        self, player_id: str, *, season: int | None = None
    ) -> tuple[int, PlayerSeasonRecord | None]:
        """Profile-only season record: never triggers live/upcoming requests."""
        current_year = self._now().astimezone(self._timezone).year
        selected = season if season is not None else current_year
        if not current_year - 4 <= selected <= current_year:
            raise AppError("invalid_request", "Season outside the five-season window", 422)
        await self._ensure_seeded()
        profile = await self._load_profile(player_id)
        record = next(
            (item for item in profile.seasons if item.season == selected), None
        )
        return selected, record

    async def _resolve_player(self, query: str) -> Player:
        resolution = await self.resolve_player(query)
        if (
            resolution.status is PlayerResolutionStatus.RESOLVED
            and resolution.player is not None
        ):
            return resolution.player
        if resolution.status is PlayerResolutionStatus.AMBIGUOUS:
            raise AppError(
                "ambiguous_player",
                "Player name is ambiguous",
                409,
                {
                    "candidates": [
                        {"id": candidate.player.id, "name": candidate.player.name}
                        for candidate in resolution.candidates
                    ]
                },
            )
        raise AppError("not_found", "Player not found", 404)

    def _mark_matches(self, outcome: CacheOutcome[object]) -> list[Match]:
        matches = cast(list[Match], outcome.value)
        if not outcome.is_stale:
            return matches
        return [
            match.model_copy(update={
                "freshness": match.freshness.model_copy(update={
                    "is_stale": True,
                    "age_seconds": outcome.age_seconds,
                }),
            })
            for match in matches
        ]

    async def _list_by_player_id(self, status: str, player_id: str | None) -> list[Match]:
        if status not in {"live", "upcoming"}:
            raise AppError("invalid_request", "Status must be live or upcoming", 422)
        if self._catalog is not None:
            # Canonical-first ordinary list read (local `api` role). The
            # bounded user-driven provider fallback in
            # `resolve_match_snapshot` is deliberately not routed through
            # this branch.
            return await self._catalog.list_matches(
                _status_for(status), player_id=player_id
            )

        async def load() -> object:
            if status == "live":
                return await self._provider.get_live_matches(player_id=player_id)
            return await self._provider.get_fixtures(player_id=player_id)

        fresh_ttl = 60 if status == "live" else 600
        stale_limit = 300 if status == "live" else 1800
        outcome = await self._cache.get_or_load(
            f"matches:{status}:{player_id or 'all'}",
            load,
            ttl=lambda value: 30 if not cast(list[Match], value) else fresh_ttl,
            stale_ttl=lambda value: 0 if not cast(list[Match], value) else stale_limit,
        )
        return self._mark_matches(outcome)

    async def list_matches(self, status: str, player_name: str | None = None) -> list[Match]:
        player = await self._resolve_player(player_name) if player_name else None
        return await self._list_by_player_id(status, player.id if player else None)

    async def list_matches_by_player_id(self, status: str, player_id: str) -> list[Match]:
        return await self._list_by_player_id(status, player_id)

    async def find_player_matches(
        self,
        player_name: str,
        time_scope: MatchTimeScope,
    ) -> list[Match]:
        player = await self._resolve_player(player_name)
        return await self.find_player_matches_by_id(player.id, time_scope)

    async def find_player_matches_by_id(
        self,
        player_id: str,
        time_scope: MatchTimeScope,
    ) -> list[Match]:
        live, upcoming = await asyncio.gather(
            self._list_by_player_id("live", player_id),
            self._list_by_player_id("upcoming", player_id),
        )
        matches = list({match.id: match for match in [*live, *upcoming]}.values())
        now_utc = self._now()
        now_local = now_utc.astimezone(self._timezone)

        def eligible(match: Match) -> bool:
            return match.status is MatchStatus.LIVE or (
                match.scheduled_at is not None and match.scheduled_at >= now_utc
            )

        def sort_key(match: Match) -> datetime:
            return match.scheduled_at or datetime.max.replace(tzinfo=timezone.utc)

        eligible_matches = [match for match in matches if eligible(match)]
        if time_scope is MatchTimeScope.NEXT:
            future = [match for match in eligible_matches if match.status is not MatchStatus.LIVE]
            return sorted(future, key=sort_key)[:1]
        if time_scope is MatchTimeScope.TODAY:
            return sorted([
                match for match in eligible_matches
                if match.scheduled_at is not None
                and match.scheduled_at.astimezone(self._timezone).date() == now_local.date()
            ], key=sort_key)

        start, end = tonight_window(now_local)
        return sorted([
            match for match in eligible_matches
            if match.scheduled_at is not None
            and start <= match.scheduled_at.astimezone(self._timezone) < end
        ], key=sort_key)

    async def get_match(self, match_id: str) -> Match:
        async def load() -> object:
            try:
                return await self._provider.get_match(match_id)
            except AppError as error:
                if error.code == "not_found":
                    return None
                raise

        def fresh_ttl(value: object) -> int:
            match = cast(Match | None, value)
            if match is None:
                return 30
            return 60 if match.status is MatchStatus.LIVE else 600

        def stale_limit(value: object) -> int:
            match = cast(Match | None, value)
            if match is None:
                return 0
            return 300 if match.status is MatchStatus.LIVE else 1800

        outcome = await self._cache.get_or_load(
            f"match:{match_id}", load, ttl=fresh_ttl, stale_ttl=stale_limit
        )
        match = cast(Match | None, outcome.value)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        if not outcome.is_stale:
            return match
        return match.model_copy(update={
            "freshness": match.freshness.model_copy(update={
                "is_stale": True,
                "age_seconds": outcome.age_seconds,
            }),
        })

    async def get_match_intelligence(
        self, match_id: str, topic: IntelligenceTopic | str
    ) -> IntelligencePacket:
        snapshot = await self.resolve_match_snapshot(match_id)
        return build_intelligence_packet(snapshot, topic=topic)

    # ------------------------------------------------------------- P2 catalog

    async def list_catalog(
        self, status: str, filters: MatchFilters | None = None
    ) -> MatchCatalog:
        if status not in {"live", "upcoming"}:
            raise AppError("invalid_request", "Status must be live or upcoming", 422)
        active = filters if filters is not None else MatchFilters.default()
        source = await self._list_by_player_id(status, None)

        def passes(
            match: Match,
            *,
            skip_circuits: bool = False,
            skip_genders: bool = False,
            skip_disciplines: bool = False,
        ) -> bool:
            tournament = match.tournament
            if (
                not skip_circuits
                and active.circuits
                and tournament.circuit not in active.circuits
            ):
                return False
            if (
                not skip_genders
                and active.genders
                and tournament.gender not in active.genders
            ):
                return False
            if (
                not skip_disciplines
                and active.disciplines
                and tournament.discipline not in active.disciplines
            ):
                return False
            return True

        selected = sorted(
            (match for match in source if passes(match)), key=catalog_sort_key
        )
        selected = await self._hydrate_matches_players(selected)
        facet_counts = FacetCounts(
            circuits={
                tier: sum(
                    1
                    for match in source
                    if passes(match, skip_circuits=True)
                    and match.tournament.circuit is tier
                )
                for tier in CircuitTier
            },
            genders={
                gender: sum(
                    1
                    for match in source
                    if passes(match, skip_genders=True)
                    and match.tournament.gender is gender
                )
                for gender in Gender
            },
            disciplines={
                discipline: sum(
                    1
                    for match in source
                    if passes(match, skip_disciplines=True)
                    and match.tournament.discipline is discipline
                )
                for discipline in Discipline
            },
        )
        return MatchCatalog(
            status=status,
            matches=tuple(selected),
            filters=active,
            facet_counts=facet_counts,
            featured_match_id=selected[0].id if selected else None,
        )

    # ------------------------------------------------------- P2 history/H2H

    async def _fetch_recent_history(self, player_id: str) -> object:
        async def load() -> object:
            try:
                return await self._provider.get_recent_results(
                    player_id, limit=HISTORY_FETCH_LIMIT
                )
            except AppError as error:
                if error.code == "unsupported":
                    return _UNSUPPORTED
                if error.code == "not_found":
                    return None
                raise

        def ttl(value: object) -> int:
            if value is _UNSUPPORTED or value is None:
                return HISTORY_EMPTY_TTL
            return HISTORY_EMPTY_TTL if not cast(list[Match], value) else HISTORY_FRESH_TTL

        outcome = await self._cache.get_or_load(
            f"history:{player_id}", load, ttl=ttl, stale_ttl=0
        )
        return outcome.value

    async def get_player_results(
        self, player_id: str, scope: str, limit: int
    ) -> PlayerResults:
        try:
            results_scope = PlayerResultsScope(scope)
        except ValueError:
            raise AppError(
                "invalid_request", "Scope must be yesterday, last, or recent", 422
            ) from None
        if not 1 <= limit <= 10:
            raise AppError("invalid_request", "Limit must be between 1 and 10", 422)

        if results_scope is not PlayerResultsScope.YESTERDAY:
            # `last`/`recent` use result-count semantics over the bounded
            # five-season window; `last` always means exactly one match.
            effective_limit = 1 if results_scope is PlayerResultsScope.LAST else limit
            matches = await self.get_latest_player_results(
                player_id, limit=effective_limit
            )
            return PlayerResults(
                player_id=player_id,
                scope=results_scope,
                availability=CapabilityStatus.AVAILABLE,
                matches=matches,
            )

        fetched = await self._fetch_recent_history(player_id)
        if fetched is None:
            raise AppError("not_found", "Player not found", 404)
        if isinstance(fetched, _UnsupportedCapability):
            return PlayerResults(
                player_id=player_id,
                scope=results_scope,
                availability=CapabilityStatus.UNAVAILABLE,
                matches=(),
            )

        matches = sorted(
            cast(list[Match], fetched),
            key=lambda match: match.scheduled_at
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        yesterday = (
            self._now().astimezone(self._timezone) - timedelta(days=1)
        ).date()
        matches = [
            match
            for match in matches
            if match.scheduled_at is not None
            and match.scheduled_at.astimezone(self._timezone).date() == yesterday
        ]
        return PlayerResults(
            player_id=player_id,
            scope=results_scope,
            availability=CapabilityStatus.AVAILABLE,
            matches=tuple(matches[:limit]),
        )

    async def get_player_results_by_name(
        self, player_name: str, scope: PlayerResultsScope | str, limit: int
    ) -> PlayerResults:
        player = await self._resolve_player(player_name)
        scope_value = scope.value if isinstance(scope, PlayerResultsScope) else scope
        return await self.get_player_results(player.id, scope_value, limit)

    async def _fetch_head_to_head(self, first_player_id: str, second_player_id: str) -> object:
        async def load() -> object:
            try:
                return await self._provider.get_head_to_head(
                    first_player_id, second_player_id, limit=HISTORY_FETCH_LIMIT
                )
            except AppError as error:
                if error.code == "unsupported":
                    return _UNSUPPORTED
                if error.code == "not_found":
                    return None
                raise

        def ttl(value: object) -> int:
            if isinstance(value, _UnsupportedCapability) or value is None:
                return HISTORY_EMPTY_TTL
            head_to_head = cast(HeadToHead, value)
            empty = not (
                head_to_head.meetings
                or head_to_head.first_player_recent
                or head_to_head.second_player_recent
            )
            return HISTORY_EMPTY_TTL if empty else HISTORY_FRESH_TTL

        outcome = await self._cache.get_or_load(
            f"h2h:{first_player_id}:{second_player_id}", load, ttl=ttl, stale_ttl=0
        )
        return outcome.value

    # ------------------------------------------------------- P2 snapshot read

    async def _cached_player_profile(self, player_id: str) -> Player | None:
        async def load() -> object:
            try:
                return await self._provider.get_player(player_id)
            except AppError:
                # A profile lookup must not make an otherwise valid match
                # snapshot unavailable.
                return None

        outcome = await self._cache.get_or_load(
            f"player-profile:{player_id}",
            load,
            ttl=lambda value: 3600 if isinstance(value, Player) else 60,
            stale_ttl=0,
        )
        return cast(Player | None, outcome.value)

    async def _hydrate_matches_players(self, matches: list[Match]) -> list[Match]:
        pending: dict[str, Player] = {}
        for match in matches:
            for player in match.players:
                if (
                    player.id not in pending
                    and (player.ranking is None or player.country_code is None)
                ):
                    pending[player.id] = player

        profiles = await asyncio.gather(
            *(self._cached_player_profile(player.id) for player in pending.values())
        )
        profile_by_id = {
            player_id: profile
            for player_id, profile in zip(pending, profiles)
            if profile is not None
        }
        if not profile_by_id:
            return matches

        hydrated: list[Match] = []
        for match in matches:
            players = tuple(
                player.model_copy(
                    update={
                        "name": (
                            profile_by_id[player.id].name
                            if profile_by_id[player.id].name != "Unknown player"
                            else player.name
                        ),
                        "country_code": (
                            profile_by_id[player.id].country_code or player.country_code
                        ),
                        "ranking": (
                            profile_by_id[player.id].ranking
                            if profile_by_id[player.id].ranking is not None
                            else player.ranking
                        ),
                    }
                )
                if player.id in profile_by_id
                else player
                for player in match.players
            )
            hydrated.append(
                match
                if players == match.players
                else match.model_copy(update={"players": players})
            )
        return hydrated

    async def _hydrate_snapshot_players(self, snapshot: MatchSnapshot) -> MatchSnapshot:
        hydrated = await self._hydrate_matches_players([snapshot.match])
        if hydrated[0] == snapshot.match:
            return snapshot
        return snapshot.model_copy(
            update={"match": hydrated[0]}
        )

    async def _normalize_snapshot(self, snapshot: MatchSnapshot) -> MatchSnapshot:
        return normalize_snapshot_quality(await self._hydrate_snapshot_players(snapshot))

    async def _persist_snapshot_upgrade(
        self, previous: MatchSnapshot, candidate: MatchSnapshot
    ) -> MatchSnapshot:
        if candidate == previous or self._snapshots is None:
            return candidate
        reduction = reduce_live_snapshot(previous, candidate)
        if not reduction.changed:
            return candidate
        await self._snapshots.save_reduction(reduction)
        return reduction.snapshot

    async def _refresh_missing_match_metadata(
        self, snapshot: MatchSnapshot
    ) -> MatchSnapshot:
        normalized = await self._normalize_snapshot(snapshot)
        normalized = await self._persist_snapshot_upgrade(snapshot, normalized)
        # Fixture/draw responses can fill these three canonical fields. The
        # current API does not expose indoor/format, so those stay null rather
        # than triggering a request that cannot improve the snapshot.
        if not any(
            value is None
            for value in (
                normalized.match.scheduled_at,
                normalized.match.round,
                normalized.match.surface,
            )
        ):
            return normalized

        async def load_optional_metadata() -> object:
            try:
                return await self._provider.get_match_snapshot(normalized.match.id)
            except AppError:
                # Existing canonical data remains usable when optional
                # enrichment is unavailable or the provider plan omits the
                # draw endpoint.
                return None

        outcome = await self._cache.get_or_load(
            f"match-metadata:{normalized.match.id}",
            load_optional_metadata,
            ttl=lambda value: 300 if isinstance(value, MatchSnapshot) else 60,
            stale_ttl=0,
        )
        candidate = cast(MatchSnapshot | None, outcome.value)
        if candidate is None:
            return normalized
        candidate = await self._normalize_snapshot(candidate)
        current_match = normalized.match
        provider_match = candidate.match
        merged_match = current_match.model_copy(
            update={
                "scheduled_at": current_match.scheduled_at or provider_match.scheduled_at,
                "round": current_match.round or provider_match.round,
                "surface": current_match.surface or provider_match.surface,
                "indoor": (
                    current_match.indoor
                    if current_match.indoor is not None
                    else provider_match.indoor
                ),
                "format": current_match.format or provider_match.format,
            }
        )
        merged = normalized.model_copy(
            update={
                "match": merged_match,
                "as_of": candidate.as_of,
            }
        )
        return await self._persist_snapshot_upgrade(normalized, merged)

    async def resolve_match_snapshot(self, match_id: str) -> MatchSnapshot:
        """Redis hot snapshot first, PostgreSQL second, provider REST last.

        A provider-resolved snapshot is persisted so later reads are PG-first.
        """
        if self._publisher is not None:
            hot = await self._publisher.get_hot_snapshot(match_id)
            if hot is not None:
                return await self._refresh_missing_match_metadata(hot)
        if self._snapshots is not None:
            stored = await self._snapshots.load_snapshot(match_id)
            if stored is not None:
                return await self._refresh_missing_match_metadata(stored)
        candidate = await self._provider.get_match_snapshot(match_id)
        candidate = await self._normalize_snapshot(candidate)
        if self._snapshots is not None:
            reduction = reduce_live_snapshot(None, candidate)
            await self._snapshots.save_reduction(reduction)
            return reduction.snapshot
        return candidate

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, limit: int
    ) -> HeadToHeadResult:
        if not 1 <= limit <= 10:
            raise AppError("invalid_request", "Limit must be between 1 and 10", 422)

        fetched = await self._fetch_head_to_head(first_player_id, second_player_id)
        if fetched is None:
            raise AppError("not_found", "Player not found", 404)
        if isinstance(fetched, _UnsupportedCapability):
            return HeadToHeadResult(
                first_player_id=first_player_id,
                second_player_id=second_player_id,
                availability=CapabilityStatus.UNAVAILABLE,
                head_to_head=None,
            )

        head_to_head = cast(HeadToHead, fetched)
        availability = (
            CapabilityStatus.PARTIAL
            if len(head_to_head.meetings) >= HISTORY_FETCH_LIMIT
            else CapabilityStatus.AVAILABLE
        )
        bounded = HeadToHead(
            first_player_id=head_to_head.first_player_id,
            second_player_id=head_to_head.second_player_id,
            meetings=head_to_head.meetings[:limit],
            first_player_recent=head_to_head.first_player_recent[:limit],
            second_player_recent=head_to_head.second_player_recent[:limit],
            freshness=head_to_head.freshness,
        )
        return HeadToHeadResult(
            first_player_id=first_player_id,
            second_player_id=second_player_id,
            availability=availability,
            head_to_head=bounded,
        )

    async def get_head_to_head_by_name(
        self, first_player_name: str, second_player_name: str, limit: int
    ) -> HeadToHeadResult:
        first_player, second_player = await asyncio.gather(
            self._resolve_player(first_player_name),
            self._resolve_player(second_player_name),
        )
        return await self.get_head_to_head(first_player.id, second_player.id, limit)


# ---------------------------------------------------------------------------
# P3 read-only query facade (T66)
# ---------------------------------------------------------------------------

_P3_OPEN_POSITION_STATUSES = frozenset({"open", "exit_pending"})
_P3_RECENT_POSITION_LIMIT = 10


def _p3_phase_from_status(status: str | None) -> str:
    if status == "live":
        return "live"
    if status == "scheduled":
        return "prematch"
    return "closed"


def _p3_decimal_text(value) -> str | None:
    return None if value is None else str(value)


class P3QueryService:
    """Assembles canonical P3 DTOs from the PostgreSQL ledger (authority)
    and the Redis hot books (fresh best bid/ask only). Internal IDs only;
    never touches provider identifiers, wallets or model internals."""

    def __init__(
        self,
        *,
        database,
        markets,
        paper,
        hot_books=None,
        quote_snapshots=None,
        snapshot_fresh_seconds: int = 300,
        realtime_fresh_seconds: int = 5,
        clock=None,
    ) -> None:
        self._database = database
        self._markets = markets
        self._paper = paper
        self._hot_books = hot_books
        self._quote_snapshots = quote_snapshots
        self._snapshot_fresh_seconds = snapshot_fresh_seconds
        self._realtime_fresh_seconds = realtime_fresh_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def _match_facts(self, match_ids) -> dict:
        """One batched lookup: players, tournament tier/gender, phase."""
        ids = {match_id for match_id in match_ids if match_id}
        if not ids:
            return {}
        from sqlalchemy import select

        from app.persistence.models import MatchRow, PlayerRow, TournamentRow

        async with self._database.session() as session:
            matches = (
                (await session.execute(select(MatchRow).where(MatchRow.id.in_(ids))))
                .scalars()
                .all()
            )
            player_ids = {
                player_id
                for row in matches
                for player_id in (row.player1_id, row.player2_id)
                if player_id
            }
            tournament_ids = {
                row.tournament_id for row in matches if row.tournament_id
            }
            players = (
                (
                    await session.execute(
                        select(PlayerRow).where(PlayerRow.id.in_(player_ids))
                    )
                )
                .scalars()
                .all()
                if player_ids
                else []
            )
            tournaments = (
                (
                    await session.execute(
                        select(TournamentRow).where(
                            TournamentRow.id.in_(tournament_ids)
                        )
                    )
                )
                .scalars()
                .all()
                if tournament_ids
                else []
            )
        player_names = {row.id: (row.localized_name or row.name) for row in players}
        tournament_by_id = {row.id: row for row in tournaments}
        facts = {}
        for row in matches:
            names = tuple(
                player_names.get(player_id)
                for player_id in (row.player1_id, row.player2_id)
            )
            tournament = tournament_by_id.get(row.tournament_id)
            facts[row.id] = {
                "player_names": (
                    (names[0], names[1])
                    if names[0] is not None and names[1] is not None
                    else None
                ),
                "player_ids": (
                    (row.player1_id, row.player2_id)
                    if row.player1_id is not None and row.player2_id is not None
                    else None
                ),
                "tier": tournament.circuit if tournament else None,
                "gender": tournament.gender if tournament else None,
                "tournament_name": tournament.name if tournament else None,
                "phase": _p3_phase_from_status(row.status),
            }
        return facts

    async def _hot_book(self, market_id: str):
        if self._hot_books is None or not market_id:
            return None
        try:
            return await self._hot_books.get_hot_book(market_id)
        except Exception:
            return None  # missing hot state degrades to None, never to zeros

    async def _bulk_hot_books(self, market_ids) -> dict:
        """One MGET for every requested market (T84: no per-row Redis calls).

        Absent hot state simply leaves the market out of the result — the
        caller degrades to the durable snapshot or to an explicit state,
        never to a fabricated book.
        """
        ids = tuple(market_id for market_id in market_ids if market_id)
        if self._hot_books is None or not ids:
            return {}
        try:
            return await self._hot_books.get_hot_books(ids)
        except Exception:
            return {}

    @staticmethod
    def _best_levels(book, outcome_player_id: str | None):
        """(best_bid, best_ask) as (player_id, price text) or None.

        Delegates to the shared canonical implementation so the papers, the
        decision workbench and the market pages format quotes identically.
        """
        return best_levels(book, outcome_player_id)

    @staticmethod
    def _outcome_levels(book, outcome_ids):
        """Per-outcome top levels aligned to outcome_ids, plus mean spread
        and top-of-book notional depth. Missing sides stay None."""
        return outcome_levels(book, outcome_ids)

    async def match_decision(self, match_id: str):
        from app.api.schemas import (
            DecisionSnapshotDto,
            GateDto,
            OutcomeLevelDto,
            PaperEventDto,
            PositionSummaryDto,
        )

        observation = await self._markets.latest_decision_observation(match_id)
        if observation is None:
            return None
        prediction = await self._markets.latest_prediction(match_id)
        position = await self._paper.get_position(match_id)
        intents = await self._paper.load_intents_for_match(match_id)
        lifecycle: list[str] = []
        for intent in intents:
            if intent.side.value == "entry":
                # Cumulative history: a filled entry passed through pending.
                lifecycle.append("entry_pending")
                if intent.status.value == "filled":
                    lifecycle.append("filled")
                elif intent.status.value == "no_fill":
                    lifecycle.append("missed")
            else:
                lifecycle.append("exit_pending")
                if intent.status.value == "filled":
                    lifecycle.append("exited")
                elif intent.status.value == "no_fill":
                    lifecycle.append("exit_missed")
        if position is not None and position.status.value == "settled":
            lifecycle.append("settled")

        # Both-side executable levels for the workbench dual comparison;
        # absent hot book degrades to an empty tuple, never to zeros.
        outcome_levels: tuple[OutcomeLevelDto, ...] = ()
        if observation.market_id:
            decision_book = await self._hot_book(observation.market_id)
            if decision_book is not None:
                outcome_levels = tuple(
                    OutcomeLevelDto(
                        player_id=side.outcome_player_id,
                        best_bid=(
                            str(side.bids[0].price) if side.bids else None
                        ),
                        best_ask=(
                            str(side.asks[0].price) if side.asks else None
                        ),
                    )
                    for side in decision_book.books
                )

        # Ledger-derived position detail and event timeline. Facts only:
        # kinds, timestamps and typed reasons; labels are presentation-side.
        position_dto = None
        if position is None and intents:
            # Intent-only lifecycle (entry pending / missed): synthesize the
            # detail from the entry intent so the workbench timeline is
            # ledger-driven; never invent numbers beyond the intent record.
            entry_intent = next(
                (item for item in intents if item.side.value == "entry"), None
            )
            if entry_intent is not None:
                intent_fill = await self._paper.get_fill_for_intent(entry_intent.id)
                intent_events = [
                    PaperEventDto(
                        id=f"{entry_intent.id}:intent",
                        kind="entry_intent",
                        at=entry_intent.created_at,
                    )
                ]
                intent_status = "entry_pending"
                if intent_fill is not None:
                    intent_events.append(
                        PaperEventDto(
                            id=f"{entry_intent.id}:fill",
                            kind=(
                                "entry_fill"
                                if intent_fill.filled
                                else "entry_no_fill"
                            ),
                            at=intent_fill.executed_at,
                            reason_code=(
                                None if intent_fill.filled else intent_fill.reason
                            ),
                        )
                    )
                    if not intent_fill.filled:
                        intent_status = "missed"
                position_dto = PositionSummaryDto(
                    position_id=entry_intent.id,
                    outcome_player_id=entry_intent.outcome_player_id,
                    status=intent_status,
                    entry_cost=str(entry_intent.stake),
                    shares=str(entry_intent.quote.shares),
                    average_entry_price=str(entry_intent.quote.average_price),
                    current_exit_value=None,
                    net_pnl=None,
                    events=tuple(intent_events),
                )
        if position is not None:
            events: list[PaperEventDto] = []
            average_entry_price = None
            for intent in intents:
                fill = await self._paper.get_fill_for_intent(intent.id)
                prefix = "entry" if intent.side.value == "entry" else "exit"
                events.append(
                    PaperEventDto(
                        id=f"{intent.id}:intent",
                        kind=f"{prefix}_intent",
                        at=intent.created_at,
                    )
                )
                if fill is not None:
                    events.append(
                        PaperEventDto(
                            id=f"{intent.id}:fill",
                            kind=(
                                f"{prefix}_fill"
                                if fill.filled
                                else f"{prefix}_no_fill"
                            ),
                            at=fill.executed_at,
                            reason_code=None if fill.filled else fill.reason,
                        )
                    )
                    if fill.filled and prefix == "entry":
                        average_entry_price = (
                            str(fill.average_price)
                            if fill.average_price is not None
                            else None
                        )
            current_exit_value = None
            net_pnl = None
            settled_at = None
            book = await self._hot_book(position.market_id)
            best_bid, _ = self._best_levels(book, position.outcome_player_id)
            if best_bid is not None:
                current_exit_value = str(position.shares * Decimal(best_bid[1]))
            for track in await self._paper.load_track_results(position.id):
                if track.track.value == "ev_exit":
                    net_pnl = str(track.net_pnl)
                    settled_at = track.settled_at
                    break
            if position.status.value == "settled":
                events.append(
                    PaperEventDto(
                        id=f"{position.id}:settled",
                        kind="settled",
                        at=settled_at or position.updated_at,
                    )
                )
            position_dto = PositionSummaryDto(
                position_id=position.id,
                outcome_player_id=position.outcome_player_id,
                status=position.status.value,
                entry_cost=str(position.entry_cost),
                shares=str(position.shares),
                average_entry_price=average_entry_price,
                current_exit_value=current_exit_value,
                net_pnl=net_pnl,
                events=tuple(events),
            )
        return DecisionSnapshotDto(
            match_id=match_id,
            market_id=observation.market_id or None,
            action=observation.action.value,
            reason_code=observation.reason_code,
            target_player_id=observation.target_player_id,
            observation_version=observation.observation_version,
            model_probabilities=(
                {
                    outcome.player_id: outcome.probability
                    for outcome in prediction.outcomes
                }
                if prediction is not None and prediction.outcomes
                else None
            ),
            model_availability=(
                prediction.availability.value if prediction is not None else None
            ),
            quote_average_price=(
                _p3_decimal_text(observation.quote.average_price)
                if observation.quote is not None
                else None
            ),
            quote_side=(
                observation.quote.side.value if observation.quote is not None else None
            ),
            conservative_net_edge=_p3_decimal_text(observation.conservative_net_edge),
            max_acceptable_price=_p3_decimal_text(observation.max_acceptable_price),
            hold_value=_p3_decimal_text(observation.hold_value),
            model_version=observation.model_version,
            calibration_version=observation.calibration_version,
            policy_version=observation.policy_version,
            data_version=(
                prediction.data_version if prediction is not None else None
            ),
            gates=tuple(
                GateDto(
                    gate=gate.gate,
                    passed=gate.passed,
                    reason_code=gate.reason_code,
                )
                for gate in observation.gates
            ),
            outcome_levels=outcome_levels,
            position=position_dto,
            lifecycle=tuple(lifecycle),
            is_stale=observation.is_stale,
            has_gap=observation.has_gap,
            lock_profit_available=observation.lock_profit_available,
            as_of=observation.as_of,
        )

    async def opportunities(self):
        from app.api.schemas import OpportunityDto

        observations = await self._markets.latest_decision_observations()
        actionable = [
            observation
            for observation in observations
            if observation.action.value in ("buy", "wait")
        ]
        facts = await self._match_facts(
            [observation.match_id for observation in actionable]
        )
        rows = []
        for observation in actionable:
            match_facts = facts.get(observation.match_id, {})
            prediction = await self._markets.latest_prediction(observation.match_id)
            model_probability = None
            if (
                prediction is not None
                and observation.target_player_id is not None
            ):
                for outcome in prediction.outcomes:
                    if outcome.player_id == observation.target_player_id:
                        model_probability = outcome.probability
                        break
            quote_price = (
                observation.quote.average_price
                if observation.quote is not None
                else None
            )
            phase = match_facts.get("phase", "closed")
            rows.append(
                (
                    0 if phase == "live" else 1,
                    0 if observation.action.value == "buy" else 1,
                    -(
                        float(observation.conservative_net_edge)
                        if observation.conservative_net_edge is not None
                        else float("-inf")
                    ),
                    OpportunityDto(
                        match_id=observation.match_id,
                        market_id=observation.market_id,
                        phase="live" if phase == "live" else "upcoming",
                        action=observation.action.value,
                        target_player_id=observation.target_player_id,
                        player_ids=match_facts.get("player_ids"),
                        player_names=match_facts.get("player_names"),
                        model_probability=model_probability,
                        executable_probability=(
                            float(quote_price) if quote_price is not None else None
                        ),
                        conservative_net_edge=_p3_decimal_text(
                            observation.conservative_net_edge
                        ),
                        max_acceptable_price=_p3_decimal_text(
                            observation.max_acceptable_price
                        ),
                        tournament_tier=match_facts.get("tier"),
                        tournament_name=match_facts.get("tournament_name"),
                        is_stale=observation.is_stale,
                        has_gap=observation.has_gap,
                        as_of=observation.as_of,
                    ),
                )
            )
        rows.sort(key=lambda item: item[:3])
        return [row[3] for row in rows]

    async def opportunity_view(self):
        """Rows plus the aggregate availability reason (spec §6.2).

        `opportunities()` keeps returning the plain row list for the Chat
        tools; the page uses this view so an empty tab can explain itself
        without ever fabricating an action.
        """
        from app.api.schemas import OpportunityAvailabilityDto

        rows = await self.opportunities()
        if rows:
            return rows, OpportunityAvailabilityDto(
                reason="HAS_OPPORTUNITIES", model_status="unknown"
            )
        observations = await self._markets.latest_decision_observations()
        unpromoted = any(
            (observation.reason_code or "") in UNPROMOTED_REASONS
            for observation in observations
        )
        if unpromoted:
            return rows, OpportunityAvailabilityDto(
                reason="ELIGIBLE_UNPROMOTED", model_status="not_promoted"
            )
        if observations and all(
            observation.is_stale or observation.has_gap
            for observation in observations
        ):
            return rows, OpportunityAvailabilityDto(
                reason="DECISION_GAP", model_status="unknown"
            )
        overviews = await self._markets.list_market_overviews()
        linked = [row for row in overviews if row.active_match_id]
        facts = await self._match_facts([row.active_match_id for row in linked])
        covered = [
            row
            for row in linked
            if facts.get(row.active_match_id, {}).get("tier") in MAIN_TOUR_TIERS
        ]
        if not covered:
            return rows, OpportunityAvailabilityDto(
                reason="NO_COVERED_MARKET", model_status="unknown"
            )
        predictions = await self._markets.latest_predictions_for_matches(
            [row.active_match_id for row in covered]
        )
        promoted = any(
            snapshot.availability.value in ("available", "degraded")
            for snapshot in predictions.values()
        )
        return rows, OpportunityAvailabilityDto(
            reason="NO_ELIGIBLE_ACTION",
            model_status="promoted" if promoted else "unknown",
        )

    async def markets(self, *, tier=None, gender=None, phase=None, page=1, page_size=20):
        from app.api.schemas import MarketPageDto, MarketQuoteDto, MarketSummaryDto

        market_rows = await self._markets.list_market_overviews()
        observations = await self._markets.latest_decision_observations()
        decision_by_match = {
            observation.match_id: observation for observation in observations
        }
        # ACTIVE links are the only match truth; every dependency below is
        # loaded in ONE bulk call regardless of row count (T84: no N+1).
        match_ids = [row.active_match_id for row in market_rows if row.active_match_id]
        facts = await self._match_facts(match_ids)
        predictions = await self._markets.latest_predictions_for_matches(match_ids)
        hot_books = await self._bulk_hot_books([row.market_id for row in market_rows])
        stored_quotes = (
            await self._quote_snapshots.load_many(
                [row.market_id for row in market_rows]
            )
            if self._quote_snapshots is not None
            else {}
        )
        summaries = []
        for row in market_rows:
            match_id = row.active_match_id
            match_facts = facts.get(match_id, {}) if match_id else {}
            market_phase = match_facts.get("phase")
            if row.status in ("closed", "resolved"):
                market_phase = "closed"
            elif market_phase is None:
                market_phase = "prematch" if row.status in ("scheduled", "open", "unknown") else "closed"
            observation = decision_by_match.get(match_id) if match_id else None
            book = hot_books.get(row.market_id)
            outcome_ids = (row.outcome_a_player_id, row.outcome_b_player_id)
            outcome_names = (row.outcome_a_name, row.outcome_b_name)
            quote = display_quote(
                hot_book=book,
                snapshot=stored_quotes.get(row.market_id),
                now=self._clock(),
                realtime_fresh_seconds=self._realtime_fresh_seconds,
                snapshot_fresh_seconds=self._snapshot_fresh_seconds,
            )
            prediction = predictions.get(match_id) if match_id else None
            model_availability = p3_model_availability(
                tier=match_facts.get("tier"),
                prediction=prediction,
                observation=observation,
            )
            model_probability = None
            if prediction is not None and row.outcome_a_player_id is not None:
                for outcome in prediction.outcomes:
                    if outcome.player_id == row.outcome_a_player_id:
                        model_probability = outcome.probability
                        break
            # Canonical directory names win; provider outcome labels are the
            # fallback so a row is never nameless when the market knows them.
            fact_ids = match_facts.get("player_ids")
            fact_names = match_facts.get("player_names")
            name_by_id = (
                dict(zip(fact_ids, fact_names, strict=False))
                if fact_ids is not None and fact_names is not None
                else {}
            )
            resolved_names = [
                (name_by_id.get(player_id) if player_id else None) or outcome_name
                for player_id, outcome_name in zip(outcome_ids, outcome_names, strict=False)
            ]
            player_names = (
                (resolved_names[0], resolved_names[1])
                if resolved_names[0] is not None and resolved_names[1] is not None
                else None
            )
            summaries.append(
                MarketSummaryDto(
                    market_id=row.market_id,
                    match_id=match_id,
                    question=row.question,
                    status=row.status,
                    tournament_name=match_facts.get("tournament_name"),
                    tier=match_facts.get("tier"),
                    gender=match_facts.get("gender"),
                    phase=market_phase,
                    model_availability=model_availability,
                    decision_action=(
                        observation.action.value if observation is not None else None
                    ),
                    reason_code=(
                        observation.reason_code if observation is not None else None
                    ),
                    player_ids=(
                        outcome_ids
                        if outcome_ids[0] is not None and outcome_ids[1] is not None
                        else None
                    ),
                    player_names=player_names,
                    model_probability=model_probability,
                    quote=MarketQuoteDto(
                        state=quote.state.value,
                        source=(
                            quote.source.value if quote.source is not None else None
                        ),
                        as_of=quote.as_of,
                        outcome_bids=quote.outcome_bids,
                        outcome_asks=quote.outcome_asks,
                        best_bid=quote.best_bid,
                        best_ask=quote.best_ask,
                        spread=quote.spread,
                        depth_usd=quote.depth_usd,
                    ),
                    is_stale=(
                        (observation.is_stale if observation is not None else False)
                        or quote.state is QuoteState.STALE
                    ),
                    has_gap=observation.has_gap if observation is not None else False,
                    as_of=row.observed_at,
                )
            )
        if tier is not None:
            summaries = [item for item in summaries if item.tier == tier]
        if gender is not None:
            summaries = [item for item in summaries if item.gender == gender]
        if phase is not None:
            summaries = [item for item in summaries if item.phase == phase]
        total = len(summaries)
        start = (page - 1) * page_size
        return MarketPageDto(
            markets=summaries[start : start + page_size],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def _position_dtos(self, positions):
        from app.api.schemas import PaperPositionDto

        facts = await self._match_facts([position.match_id for position in positions])
        hot_books = await self._bulk_hot_books(
            [position.market_id for position in positions]
        )
        rows = []
        for position in positions:
            book = hot_books.get(position.market_id)
            best_bid, _ = self._best_levels(book, position.outcome_player_id)
            current_exit_value = None
            freshness = position.updated_at
            if best_bid is not None:
                current_exit_value = str(
                    position.shares * Decimal(best_bid[1])
                )
                freshness = book.received_at
            net_pnl = None
            if position.status.value == "settled":
                for track in await self._paper.load_track_results(position.id):
                    if track.track.value == "ev_exit":
                        net_pnl = str(track.net_pnl)
                        break
            average_entry_price = None
            for intent in await self._paper.load_intents_for_match(position.match_id):
                if intent.side.value != "entry":
                    continue
                fill = await self._paper.get_fill_for_intent(intent.id)
                if fill is not None and fill.filled and fill.average_price is not None:
                    average_entry_price = str(fill.average_price)
                break
            match_facts = facts.get(position.match_id, {})
            rows.append(
                PaperPositionDto(
                    position_id=position.id,
                    match_id=position.match_id,
                    market_id=position.market_id,
                    tournament_name=match_facts.get("tournament_name"),
                    outcome_player_id=position.outcome_player_id,
                    player_ids=match_facts.get("player_ids"),
                    player_names=match_facts.get("player_names"),
                    status=position.status.value,
                    entry_cost=str(position.entry_cost),
                    shares=str(position.shares),
                    average_entry_price=average_entry_price,
                    current_exit_value=current_exit_value,
                    net_pnl=net_pnl,
                    freshness_as_of=freshness,
                )
            )
        return rows

    async def _pending_entry_rows(self, excluded_match_ids):
        """Ledger-derived entry_pending rows: pending entry intents that have
        no position yet. Never reconstructed from browser state."""
        from app.api.schemas import PaperPositionDto

        pending = await self._paper.load_pending_intents()
        intents = sorted(
            (
                intent
                for intent in pending
                if intent.side.value == "entry"
                and intent.match_id not in excluded_match_ids
            ),
            key=lambda intent: intent.created_at,
            reverse=True,
        )
        if not intents:
            return []
        facts = await self._match_facts([intent.match_id for intent in intents])
        rows = []
        for intent in intents:
            match_facts = facts.get(intent.match_id, {})
            rows.append(
                PaperPositionDto(
                    position_id=intent.id,
                    match_id=intent.match_id,
                    market_id=intent.market_id,
                    tournament_name=match_facts.get("tournament_name"),
                    outcome_player_id=intent.outcome_player_id,
                    player_ids=match_facts.get("player_ids"),
                    player_names=match_facts.get("player_names"),
                    status="entry_pending",
                    entry_cost=str(intent.stake),
                    shares=str(intent.quote.shares),
                    average_entry_price=str(intent.quote.average_price),
                    current_exit_value=None,
                    net_pnl=None,
                    freshness_as_of=intent.created_at,
                )
            )
        return rows

    async def paper_positions(self):
        positions = await self._paper.load_all_positions()
        open_positions = [
            position
            for position in positions
            if position.status.value in _P3_OPEN_POSITION_STATUSES
        ]
        recent = [
            position
            for position in positions
            if position.status.value not in _P3_OPEN_POSITION_STATUSES
        ][:_P3_RECENT_POSITION_LIMIT]
        open_rows = await self._position_dtos(open_positions)
        open_rows.extend(
            await self._pending_entry_rows(
                {position.match_id for position in positions}
            )
        )
        return {
            "open": open_rows,
            "recent": await self._position_dtos(recent),
        }

    @staticmethod
    def _pulse_urgency(position, decision):
        """Most urgent open position first: an actionable SELL, then a
        lock-profit exit, then stale/gap overlays, then plain holds."""
        if decision is not None and decision.action == "sell":
            first = 0
        elif decision is not None and decision.lock_profit_available:
            first = 1
        elif decision is not None and (decision.is_stale or decision.has_gap):
            first = 2
        elif position.status == "exit_pending":
            first = 3
        elif position.status == "entry_pending":
            first = 5
        else:
            first = 4
        freshness = (
            position.freshness_as_of.timestamp()
            if position.freshness_as_of is not None
            else 0.0
        )
        decision_recency = (
            decision.as_of.timestamp() if decision is not None else 0.0
        )
        return (first, -decision_recency, -freshness, position.position_id)

    async def pulse(self):
        from app.api.schemas import PulseRowDto

        view = await self.paper_positions()
        open_rows = view["open"]
        rows = []
        if open_rows:
            # Reserve exactly one row for the most urgent open position,
            # then fill the remaining slots with the strongest opportunities.
            best = None
            for position in open_rows:
                decision = await self.match_decision(position.match_id)
                key = self._pulse_urgency(position, decision)
                if best is None or key < best[0]:
                    best = (key, position, decision)
            _, position, decision = best
            facts = (await self._match_facts([position.match_id])).get(
                position.match_id, {}
            )
            phase = facts.get("phase")
            if phase == "prematch":
                phase = "upcoming"
            rows.append(
                PulseRowDto(
                    match_id=position.match_id,
                    market_id=position.market_id,
                    kind="position",
                    action=(decision.action if decision is not None else "hold"),
                    phase=phase,
                    player_names=position.player_names,
                    model_probability=(
                        None
                        if decision is None
                        or decision.model_probabilities is None
                        else decision.model_probabilities.get(
                            position.outcome_player_id
                        )
                    ),
                    executable_probability=(
                        float(
                            (
                                Decimal(position.current_exit_value)
                                / Decimal(position.shares)
                            ).quantize(Decimal("0.0001"))
                        )
                        if position.current_exit_value is not None
                        else None
                    ),
                    conservative_net_edge=(
                        decision.conservative_net_edge
                        if decision is not None
                        else None
                    ),
                    tournament_name=facts.get("tournament_name"),
                    is_stale=decision.is_stale if decision is not None else False,
                    has_gap=decision.has_gap if decision is not None else False,
                    as_of=position.freshness_as_of,
                )
            )
        for opportunity in (await self.opportunities())[: 3 - len(rows)]:
            rows.append(
                PulseRowDto(
                    match_id=opportunity.match_id,
                    market_id=opportunity.market_id,
                    kind="opportunity",
                    action=opportunity.action,
                    phase=opportunity.phase,
                    player_names=opportunity.player_names,
                    model_probability=opportunity.model_probability,
                    executable_probability=opportunity.executable_probability,
                    conservative_net_edge=opportunity.conservative_net_edge,
                    tournament_name=opportunity.tournament_name,
                    is_stale=opportunity.is_stale,
                    has_gap=opportunity.has_gap,
                    as_of=opportunity.as_of,
                )
            )
        return {"data": rows[:3], "has_open_position": bool(open_rows)}

    async def markets_snapshot(self):
        market_rows = await self._markets.list_market_overviews()
        observations = await self._markets.latest_decision_observations()
        actionable = sum(
            1
            for observation in observations
            if observation.action.value in ("buy", "wait")
        )
        positions = await self._paper.load_all_positions()
        open_positions = sum(
           1
            for position in positions
            if position.status.value in _P3_OPEN_POSITION_STATUSES
        )
        _, availability = await self.opportunity_view()
        return {
            "markets": len(market_rows),
            "opportunities": actionable,
            "open_positions": open_positions,
            "availability": availability.reason,
        }
