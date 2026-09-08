"""TennisService: player resolution, Asia/Macau time scopes, cache policy.

The service is the single source of truth for REST and chat tools. It never
exposes provider DTOs, and time semantics live here as tested service rules
rather than prompt instructions.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from enum import StrEnum
from typing import cast
from zoneinfo import ZoneInfo

from app.cache import AsyncTTLCache, CacheOutcome
from app.domain import Match, MatchStatus, Player
from app.errors import AppError
from app.providers.base import TennisDataProvider


class MatchTimeScope(StrEnum):
    TODAY = "today"
    TONIGHT = "tonight"
    NEXT = "next"


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
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._now = now
        self._timezone = ZoneInfo(timezone)

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

    async def _resolve_player(self, query: str) -> Player:
        players = await self.search_players(query)
        individuals = [player for player in players if not _is_composite_player_name(player.name)]
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
        candidates = exact or normalized_players
        if not candidates:
            raise AppError("not_found", "Player not found", 404)
        if len(candidates) > 1:
            raise AppError(
                "ambiguous_player",
                "Player name is ambiguous",
                409,
                {"candidates": [{"id": player.id, "name": player.name} for player in candidates]},
            )
        return candidates[0]

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

    async def find_player_matches(
        self,
        player_name: str,
        time_scope: MatchTimeScope,
    ) -> list[Match]:
        player = await self._resolve_player(player_name)
        live, upcoming = await asyncio.gather(
            self._list_by_player_id("live", player.id),
            self._list_by_player_id("upcoming", player.id),
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
