"""LiveTennisAPI Free adapter.

Owns authentication, HTTP behavior, vendor DTO validation, player-major score
parsing, UTC timestamps, server normalization, lifecycle mapping, nullable
fields, external-ID extraction, and forward-compatible ignoring of unknown
fields. Vendor payloads stop here: only canonical domain models are returned.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain import (
    DataFreshness,
    LiveMatchState,
    Match,
    MatchScore,
    MatchStatus,
    Player,
    SetScore,
    Tournament,
)
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.livetennis_dtos import (
    ListResponse,
    LiveFixtureDto,
    LiveMatchDto,
    LivePlayerDto,
    LiveScoreDto,
)

PROVIDER_NAME = "livetennis"

STATUS_MAP = {
    "upcoming": MatchStatus.SCHEDULED,
    "scheduled": MatchStatus.SCHEDULED,
    "live": MatchStatus.LIVE,
    "completed": MatchStatus.FINISHED,
    "cancelled": MatchStatus.CANCELLED,
}

EVENT_STATUS_MAP = {
    "postponed": MatchStatus.POSTPONED,
    "cancelled": MatchStatus.CANCELLED,
}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def map_score(dto: LiveScoreDto) -> MatchScore:
    p1_games, p2_games = (dto.games + [[], []])[:2]
    set_count = max(len(p1_games), len(p2_games))
    sets = tuple(
        SetScore(
            number=index + 1,
            player1_games=p1_games[index] if index < len(p1_games) else None,
            player2_games=p2_games[index] if index < len(p2_games) else None,
        )
        for index in range(set_count)
    )
    points = tuple((dto.points + [None, None])[:2])
    return MatchScore(
        sets_won=tuple((dto.sets + [0, 0])[:2]),
        sets=sets,
        points=points,
        is_tiebreak=dto.is_tiebreak,
    )


class LiveTennisProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        identities: MemoryIdentityRepository,
        api_key: str,
        now: Callable[[], datetime],
    ) -> None:
        self._client = client
        self._identities = identities
        self._api_key = api_key
        self._now = now
        self._match_players: dict[str, tuple[str, str]] = {}

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.get(
                path, params=params, headers={"X-API-Key": self._api_key}
            )
        except httpx.HTTPError as error:
            raise AppError(
                "provider_unavailable", "LiveTennisAPI request failed", 503
            ) from error

        if response.status_code == 404:
            raise AppError("not_found", "Provider resource not found", 404)
        if response.status_code == 429:
            raise AppError(
                "rate_limited",
                "LiveTennisAPI quota exceeded",
                429,
                {"retry_after": response.headers.get("Retry-After")},
            )
        if response.status_code == 403:
            raise AppError(
                "provider_unavailable",
                "Provider plan does not support this request",
                503,
            )
        if response.status_code >= 400:
            raise AppError("provider_unavailable", "LiveTennisAPI request failed", 503)

        try:
            return response.json()
        except ValueError as error:
            raise AppError(
                "provider_unavailable",
                "LiveTennisAPI response was not valid JSON",
                503,
            ) from error

    def _validate(self, model: type, payload: Any) -> Any:
        try:
            return model.model_validate(payload)
        except ValidationError as error:
            raise AppError(
                "provider_unavailable",
                "LiveTennisAPI response validation failed",
                503,
            ) from error

    def _map_player(self, dto: LivePlayerDto, fallback_external_id: str) -> Player:
        external_id = str(dto.id) if dto.id is not None else fallback_external_id
        return Player(
            id=self._identities.get_or_create("player", PROVIDER_NAME, external_id),
            name=dto.name,
            country_code=dto.country,
            ranking=dto.ranking,
        )

    @staticmethod
    def _map_status(dto: LiveMatchDto | LiveFixtureDto) -> MatchStatus:
        event_status = (dto.event_status or "").strip().casefold()
        if event_status in EVENT_STATUS_MAP:
            return EVENT_STATUS_MAP[event_status]
        status = (dto.status or "").strip().casefold()
        return STATUS_MAP.get(status, MatchStatus.UNKNOWN)

    @staticmethod
    def _player_slot_id(index: int | None, player_ids: tuple[str, str]) -> str | None:
        if index == 1:
            return player_ids[0]
        if index == 2:
            return player_ids[1]
        return None

    def _map_match(self, dto: LiveMatchDto | LiveFixtureDto) -> Match | None:
        p1_dto = dto.players.get("p1")
        p2_dto = dto.players.get("p2")
        if p1_dto is None or p2_dto is None:
            return None

        match_id = self._identities.get_or_create("match", PROVIDER_NAME, str(dto.id))
        p1 = self._map_player(p1_dto, f"fixture:{dto.id}:p1")
        p2 = self._map_player(p2_dto, f"fixture:{dto.id}:p2")
        player_ids = (p1.id, p2.id)
        self._match_players[match_id] = player_ids

        tournament = Tournament(
            id=self._identities.get_or_create(
                "tournament",
                PROVIDER_NAME,
                dto.tournament_id or dto.tournament or str(dto.id),
            ),
            name=dto.tournament,
            tour=dto.tour,
        )

        live_state = None
        if dto.score is not None:
            live_state = LiveMatchState(
                score=map_score(dto.score),
                server_player_id=self._player_slot_id(dto.score.server, player_ids),
            )

        return Match(
            id=match_id,
            status=self._map_status(dto),
            players=(p1, p2),
            tournament=tournament,
            scheduled_at=parse_timestamp(dto.scheduled_time),
            round=dto.round,
            surface=dto.surface,
            indoor=dto.indoor,
            format=dto.format,
            live_state=live_state,
            winner_player_id=self._player_slot_id(dto.winner, player_ids),
            freshness=DataFreshness(
                provider=PROVIDER_NAME,
                source_updated_at=(
                    parse_timestamp(dto.score.timestamp) if dto.score else None
                ),
                observed_at=self._now(),
            ),
        )

    def _map_list(self, payload: Any, item_model: type) -> list:
        listing = self._validate(ListResponse[item_model], payload)  # type: ignore[valid-type]
        mapped = []
        for dto in listing.data:
            match = self._map_match(dto)
            if match is not None:
                mapped.append(match)
        return mapped

    @staticmethod
    def _filter(matches: list[Match], player_id: str | None) -> list[Match]:
        if player_id is None:
            return list(matches)
        return [
            match
            for match in matches
            if any(player.id == player_id for player in match.players)
        ]

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        payload = await self._request("/matches", {"status": "live"})
        return self._filter(self._map_list(payload, LiveMatchDto), player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        payload = await self._request("/fixtures")
        return self._filter(self._map_list(payload, LiveFixtureDto), player_id)

    async def search_players(self, query: str) -> list[Player]:
        payload = await self._request("/players", {"search": query})
        listing = self._validate(ListResponse[LivePlayerDto], payload)
        players = []
        for dto in listing.data:
            if dto.id is None:
                continue
            players.append(
                Player(
                    id=self._identities.get_or_create(
                        "player", PROVIDER_NAME, str(dto.id)
                    ),
                    name=dto.name,
                    country_code=dto.country,
                    ranking=dto.ranking,
                )
            )
        return players

    async def get_match(self, match_id: str) -> Match:
        external_id = self._identities.external_id("match", PROVIDER_NAME, match_id)
        if external_id is None:
            raise AppError("not_found", "Match not found", 404)
        payload = await self._request(f"/matches/{external_id}")
        dto = self._validate(LiveMatchDto, payload)
        match = self._map_match(dto)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_score(self, match_id: str) -> LiveMatchState:
        external_id = self._identities.external_id("match", PROVIDER_NAME, match_id)
        if external_id is None:
            raise AppError("not_found", "Match not found", 404)
        payload = await self._request(f"/matches/{external_id}/score")
        dto = self._validate(LiveScoreDto, payload)

        player_ids = self._match_players.get(match_id)
        if player_ids is None:
            match = await self.get_match(match_id)
            player_ids = (match.players[0].id, match.players[1].id)

        return LiveMatchState(
            score=map_score(dto),
            server_player_id=self._player_slot_id(dto.server, player_ids),
        )
