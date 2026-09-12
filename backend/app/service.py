"""TennisService: player resolution, Asia/Macau time scopes, cache policy.

The service is the single source of truth for REST and chat tools. It never
exposes provider DTOs, and time semantics live here as tested service rules
rather than prompt instructions.
"""

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
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
from app.players.models import (
    PlayerAliasKind,
    PlayerCandidate,
    PlayerProfileData,
    PlayerProfileView,
    PlayerResolution,
    PlayerResolutionStatus,
    PlayerResultPage,
    RankingPage,
    ResultOutcome,
    Tour,
)
from app.providers.base import TennisDataProvider
from app.realtime.reducer import normalize_snapshot_quality, reduce_live_snapshot


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
                "invalid_request", "Scope must be yesterday or recent", 422
            ) from None
        if not 1 <= limit <= 10:
            raise AppError("invalid_request", "Limit must be between 1 and 10", 422)

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
        if results_scope is PlayerResultsScope.YESTERDAY:
            yesterday = (
                self._now().astimezone(self._timezone) - timedelta(days=1)
            ).date()
            matches = [
                match
                for match in matches
                if match.scheduled_at is not None
                and match.scheduled_at.astimezone(self._timezone).date() == yesterday
            ]
            availability = CapabilityStatus.AVAILABLE
        else:
            availability = (
                CapabilityStatus.PARTIAL
                if len(matches) >= HISTORY_FETCH_LIMIT
                else CapabilityStatus.AVAILABLE
            )
        return PlayerResults(
            player_id=player_id,
            scope=results_scope,
            availability=availability,
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
