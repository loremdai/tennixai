"""API-Tennis REST adapter (P2 default provider).

Owns request parameters, response validation, error translation, timezone
normalization (all requests use GMT → canonical UTC), event taxonomy, and
vendor-to-canonical mapping. Vendor payloads stop here: only canonical domain
models are returned, and diagnostics never include the API key or full URLs.
The mapping helpers are module-level so the WebSocket live feed shares them.
"""

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from app.domain import (
    CapabilityStatus,
    DataFreshness,
    DataQuality,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    MatchStatus,
    Player,
    PointEvent,
    SetScore,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.errors import AppError
from app.identity import IdentityRepository
from app.providers.api_tennis_classification import classify_event_type
from app.providers.api_tennis_dtos import (
    ApiTennisResponse,
    HeadToHeadDto,
    MatchDto,
    PlayerDto,
)

PROVIDER_NAME = "api_tennis"

UPCOMING_WINDOW_DAYS = 7
SEARCH_WINDOW_DAYS = 3
RECENT_RESULTS_WINDOW_DAYS = 30
SEARCH_RESULT_LIMIT = 20

FIRST_PLAYER_TOKENS = ("first player", "first play", "player 1", "1")
SECOND_PLAYER_TOKENS = ("second player", "second play", "player 2", "2")

POINT_VALUES = {"0": 0, "15": 15, "30": 30, "40": 40, "a": 41, "adv": 41, "45": 41}

# Vendor stat_name (casefolded) → (canonical name, unit). Unknown names are
# recorded nowhere public; "Last 10 balls" is deliberately unmapped (spec §5.4).
STAT_NAME_MAP: dict[str, tuple[StatisticName, str]] = {
    "aces": (StatisticName.ACES, "count"),
    "double faults": (StatisticName.DOUBLE_FAULTS, "count"),
    "1st serve percentage": (StatisticName.FIRST_SERVE_PERCENTAGE, "percent"),
    "1st serve points won": (StatisticName.FIRST_SERVE_POINTS_WON, "percent"),
    "2nd serve points won": (StatisticName.SECOND_SERVE_POINTS_WON, "percent"),
    "service points won": (StatisticName.SERVICE_POINTS_WON, "percent"),
    "service games won": (StatisticName.SERVICE_GAMES_WON, "percent"),
    "break points saved": (StatisticName.BREAK_POINTS_SAVED, "percent"),
    "break points converted": (StatisticName.BREAK_POINTS_CONVERTED, "percent"),
    "return points won": (StatisticName.RETURN_POINTS_WON, "percent"),
    "1st return points won": (StatisticName.FIRST_RETURN_POINTS_WON, "percent"),
    "2nd return points won": (StatisticName.SECOND_RETURN_POINTS_WON, "percent"),
    "return games won": (StatisticName.RETURN_GAMES_WON, "percent"),
    "winners": (StatisticName.WINNERS, "count"),
    "unforced errors": (StatisticName.UNFORCED_ERRORS, "count"),
    "net points won": (StatisticName.NET_POINTS_WON, "percent"),
    "total points won": (StatisticName.TOTAL_POINTS_WON, "percent"),
    "total games won": (StatisticName.TOTAL_GAMES_WON, "percent"),
    "match points saved": (StatisticName.MATCH_POINTS_SAVED, "count"),
    "average 1st serve speed": (StatisticName.AVERAGE_FIRST_SERVE_SPEED, "km/h"),
    "average 2nd serve speed": (StatisticName.AVERAGE_SECOND_SERVE_SPEED, "km/h"),
    "distance covered": (StatisticName.DISTANCE_COVERED, "m"),
}

TERMINAL_STATUSES = frozenset(
    {MatchStatus.FINISHED, MatchStatus.CANCELLED, MatchStatus.POSTPONED}
)


def map_status(event_status: str | None) -> MatchStatus:
    text = (event_status or "").strip().casefold()
    if text in {"", "1", "0", "-", "not started", "scheduled", "vs", "vs."}:
        return MatchStatus.SCHEDULED
    if text.startswith("set ") or text in {"live", "in progress", "in play"}:
        return MatchStatus.LIVE
    if text in {"finished", "retired", "walk over", "walkover", "wo", "ret."}:
        return MatchStatus.FINISHED
    if text in {"cancelled", "canceled", "abandoned"}:
        return MatchStatus.CANCELLED
    if text in {"postponed"}:
        return MatchStatus.POSTPONED
    return MatchStatus.UNKNOWN


def parse_int_pair(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", raw)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def parse_point_pair(raw: str | None) -> tuple[str, str] | None:
    if not raw:
        return None
    match = re.fullmatch(r"\s*([0-9A-Za-z]+)\s*-\s*([0-9A-Za-z]+)\s*", raw)
    if match is None:
        return None
    return match.group(1), match.group(2)


def parse_scheduled_at(date_raw: str | None, time_raw: str | None) -> datetime | None:
    """Vendor times are requested with timezone=GMT, so they are UTC."""
    if not date_raw:
        return None
    try:
        date_part = datetime.strptime(date_raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    if not time_raw:
        # A date without a time is not a start time; do not invent midnight.
        return None
    try:
        time_part = datetime.strptime(time_raw.strip(), "%H:%M").time()
    except ValueError:
        return None
    return datetime.combine(date_part, time_part, tzinfo=timezone.utc)


def slot_player_id(token: str | None, player_ids: tuple[str, str]) -> str | None:
    text = (token or "").strip().casefold()
    if not text:
        return None
    if text in FIRST_PLAYER_TOKENS:
        return player_ids[0]
    if text in SECOND_PLAYER_TOKENS:
        return player_ids[1]
    return None


def map_period(stat_period: str | None) -> str | None:
    text = (stat_period or "").strip().casefold()
    if text == "match":
        return "match"
    match = re.fullmatch(r"set\s*:?(\d+)", text)
    if match is not None:
        return f"set:{match.group(1)}"
    return None


def parse_stat_value(raw: str | None) -> float | None:
    text = (raw or "").strip()
    if not text or text == "-":
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return float(text)
    except ValueError:
        return None


def point_value(token: str) -> int | None:
    return POINT_VALUES.get(token.strip().casefold())


# ------------------------------------------------------------------- mapping


async def map_player(
    identities: IdentityRepository, dto: PlayerDto, fallback_external_id: str
) -> Player:
    external_id = (
        str(dto.player_key) if dto.player_key is not None else fallback_external_id
    )
    return Player(
        id=await identities.get_or_create("player", PROVIDER_NAME, external_id),
        name=(dto.player_name or "").strip() or "Unknown player",
        # The vendor supplies country names, not codes; canonical code stays
        # unavailable rather than guessing.
        country_code=None,
        ranking=None,
    )


def map_live_state(
    dto: MatchDto, player_ids: tuple[str, str], status: MatchStatus
) -> LiveMatchState | None:
    sets_won = parse_int_pair(dto.event_final_result)
    set_rows = [
        SetScore(
            number=int(row.score_set) if (row.score_set or "").isdigit() else index + 1,
            player1_games=(
                int(row.score_first) if (row.score_first or "").isdigit() else None
            ),
            player2_games=(
                int(row.score_second) if (row.score_second or "").isdigit() else None
            ),
        )
        for index, row in enumerate(dto.scores)
    ]
    points = parse_point_pair(dto.event_game_result)
    if status not in {MatchStatus.LIVE, MatchStatus.FINISHED}:
        # The vendor pre-seeds 0-0 set rows for scheduled matches; only a
        # real final/game score justifies a live state before the match
        # starts.
        if sets_won is None and points is None:
            return None
    score = MatchScore(
        sets_won=sets_won or (0, 0),
        sets=tuple(set_rows),
        points=points or (None, None),
        is_tiebreak=False,
    )
    return LiveMatchState(
        score=score,
        server_player_id=slot_player_id(dto.event_serve, player_ids),
        state_version=0,
    )


async def map_match(
    dto: MatchDto, identities: IdentityRepository, now: Callable[[], datetime]
) -> Match | None:
    if dto.first_player_key is None or dto.second_player_key is None:
        return None

    match_id = await identities.get_or_create(
        "match", PROVIDER_NAME, str(dto.event_key)
    )
    p1 = await map_player(
        identities,
        PlayerDto(player_key=dto.first_player_key, player_name=dto.event_first_player),
        f"fixture:{dto.event_key}:p1",
    )
    p2 = await map_player(
        identities,
        PlayerDto(player_key=dto.second_player_key, player_name=dto.event_second_player),
        f"fixture:{dto.event_key}:p2",
    )
    player_ids = (p1.id, p2.id)

    tournament_external = (
        dto.tournament_key if dto.tournament_key is not None else dto.event_key
    )
    circuit, gender, discipline = classify_event_type(dto.event_type_type)
    tournament = Tournament(
        id=await identities.get_or_create(
            "tournament", PROVIDER_NAME, str(tournament_external)
        ),
        name=(dto.tournament_name or "").strip() or "Unknown tournament",
        tour=None,
        circuit=circuit,
        gender=gender,
        discipline=discipline,
    )

    status = map_status(dto.event_status)
    live_state = map_live_state(dto, player_ids, status)

    return Match(
        id=match_id,
        status=status,
        players=(p1, p2),
        tournament=tournament,
        scheduled_at=parse_scheduled_at(dto.event_date, dto.event_time),
        round=dto.tournament_round,
        surface=None,
        indoor=None,
        format=None,
        live_state=live_state,
        winner_player_id=slot_player_id(dto.event_winner, player_ids),
        freshness=DataFreshness(
            provider=PROVIDER_NAME,
            source_updated_at=None,
            observed_at=now(),
        ),
    )


def map_points(
    dto: MatchDto,
    match_id: str,
    player_ids: tuple[str, str],
    now: Callable[[], datetime],
) -> list[PointEvent]:
    observed_at = now()
    points: list[PointEvent] = []
    sequence = 0
    last_known_set = 1
    for game in dto.pointbypoint:
        set_number = _leading_int(game.set_number)
        if set_number is None:
            set_number = last_known_set
        else:
            last_known_set = set_number
        game_number = _leading_int(game.number_game) or (
            (points[-1].game_number + 1) if points else 1
        )
        server_id = slot_player_id(game.player_served, player_ids)
        before: tuple[int, int] = (0, 0)
        before_raw = ("0", "0")
        for raw_point in game.points:
            parsed = parse_point_pair(raw_point.score)
            if parsed is None:
                continue
            values = (point_value(parsed[0]), point_value(parsed[1]))
            if values[0] is None or values[1] is None:
                continue
            after: tuple[int, int] = (values[0], values[1])  # type: ignore[assignment]
            sequence += 1
            winner_id = _derive_point_winner(before, after, player_ids)
            quality = None
            if winner_id is None:
                quality = DataQuality(
                    capability="point_winner",
                    status=CapabilityStatus.PARTIAL,
                    provider=PROVIDER_NAME,
                    reason="winner_indeterminate",
                    observed_at=observed_at,
                )
            fingerprint_source = json.dumps(
                {
                    "set": set_number,
                    "game": game_number,
                    "point": _leading_int(raw_point.number_point) or sequence,
                    "score": raw_point.score,
                    "served": game.player_served,
                    "bp": raw_point.break_point,
                    "sp": raw_point.set_point,
                    "mp": raw_point.match_point,
                },
                sort_keys=True,
            )
            points.append(
                PointEvent(
                    id=f"pe_{match_id}_{sequence}",
                    match_id=match_id,
                    sequence=sequence,
                    set_number=set_number,
                    game_number=game_number,
                    point_number=_leading_int(raw_point.number_point) or sequence,
                    server_player_id=server_id,
                    winner_player_id=winner_id,
                    score_before=MatchScore(
                        sets_won=(0, 0), sets=(), points=before_raw
                    ),
                    score_after=MatchScore(sets_won=(0, 0), sets=(), points=parsed),
                    is_break_point=raw_point.break_point is not None,
                    is_set_point=raw_point.set_point is not None,
                    is_match_point=raw_point.match_point is not None,
                    observed_at=observed_at,
                    provider=PROVIDER_NAME,
                    source_fingerprint=hashlib.sha256(
                        fingerprint_source.encode("utf-8")
                    ).hexdigest()[:32],
                    revision=1,
                    quality=quality,
                )
            )
            before = after
            before_raw = parsed
    return points


def _derive_point_winner(
    before: tuple[int, int], after: tuple[int, int], player_ids: tuple[str, str]
) -> str | None:
    first_changed = after[0] != before[0]
    second_changed = after[1] != before[1]
    if first_changed and not second_changed and after[0] > before[0]:
        return player_ids[0]
    if second_changed and not first_changed and after[1] > before[1]:
        return player_ids[1]
    return None


def map_statistics(
    dto: MatchDto,
    match_id: str,
    player_keys: tuple[str, str],
    now: Callable[[], datetime],
) -> list[MatchStatistic]:
    observed_at = now()
    merged: dict[tuple[StatisticName, str], dict[str, Any]] = {}
    for stat in dto.statistics:
        name_raw = (stat.stat_name or "").strip().casefold()
        mapped = STAT_NAME_MAP.get(name_raw)
        period = map_period(stat.stat_period)
        if mapped is None or period is None:
            continue
        value = parse_stat_value(stat.stat_value)
        if value is None:
            continue
        canonical_name, unit = mapped
        key_slot = str(stat.player_key)
        entry = merged.setdefault(
            (canonical_name, period),
            {"unit": unit, "player1_value": None, "player2_value": None},
        )
        if key_slot == player_keys[0]:
            entry["player1_value"] = value
        elif key_slot == player_keys[1]:
            entry["player2_value"] = value
    statistics = []
    for (canonical_name, period), entry in sorted(
        merged.items(), key=lambda item: (item[0][1], item[0][0].value)
    ):
        both = entry["player1_value"] is not None and entry["player2_value"] is not None
        statistics.append(
            MatchStatistic(
                match_id=match_id,
                name=canonical_name,
                period=period,
                player1_value=entry["player1_value"],
                player2_value=entry["player2_value"],
                unit=entry["unit"],
                provenance=StatisticProvenance.PROVIDER,
                availability=(
                    CapabilityStatus.AVAILABLE if both else CapabilityStatus.PARTIAL
                ),
                as_of=observed_at,
            )
        )
    return statistics


def build_snapshot_quality(
    has_points: bool, has_statistics: bool, now: Callable[[], datetime]
) -> tuple[DataQuality, ...]:
    observed_at = now()
    return (
        DataQuality(
            capability="point_by_point",
            status=(
                CapabilityStatus.AVAILABLE
                if has_points
                else CapabilityStatus.UNAVAILABLE
            ),
            provider=PROVIDER_NAME,
            reason=None if has_points else "not_reported",
            observed_at=observed_at,
        ),
        DataQuality(
            capability="statistics",
            status=(
                CapabilityStatus.AVAILABLE
                if has_statistics
                else CapabilityStatus.UNAVAILABLE
            ),
            provider=PROVIDER_NAME,
            reason=None if has_statistics else "not_reported",
            observed_at=observed_at,
        ),
        DataQuality(
            capability="momentum",
            status=CapabilityStatus.UNAVAILABLE,
            provider=PROVIDER_NAME,
            reason="not_computed",
            observed_at=observed_at,
        ),
    )


def _leading_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    match = re.search(r"\d+", str(raw))
    return int(match.group(0)) if match else None


async def map_livescore_row_to_snapshot(
    dto: MatchDto, identities: IdentityRepository, now: Callable[[], datetime]
) -> MatchSnapshot | None:
    match = await map_match(dto, identities, now)
    if match is None:
        return None
    player_ids = (match.players[0].id, match.players[1].id)
    player_keys = (str(dto.first_player_key), str(dto.second_player_key))
    points = tuple(map_points(dto, match.id, player_ids, now))
    statistics = tuple(map_statistics(dto, match.id, player_keys, now))
    live_state = match.live_state
    return MatchSnapshot(
        match=match,
        points=points,
        statistics=statistics,
        momentum=(),
        quality=build_snapshot_quality(bool(points), bool(statistics), now),
        state_version=live_state.state_version if live_state is not None else 0,
        as_of=now(),
    )


# ------------------------------------------------------------------ provider


class ApiTennisProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        identities: IdentityRepository,
        api_key: str,
        now: Callable[[], datetime],
    ) -> None:
        self._client = client
        self._identities = identities
        self._api_key = api_key
        self._now = now

    async def _request(
        self, method: str, extra_params: dict[str, Any] | None = None
    ) -> Any:
        params: dict[str, Any] = {"method": method}
        if extra_params:
            params.update(extra_params)
        # The key is injected last, after any diagnostics-friendly metadata.
        params["APIkey"] = self._api_key
        try:
            response = await self._client.get("", params=params)
        except httpx.HTTPError as error:
            raise AppError(
                "provider_unavailable",
                f"API-Tennis request failed ({type(error).__name__})",
                503,
            ) from error

        if response.status_code == 404:
            raise AppError("not_found", "Provider resource not found", 404)
        if response.status_code == 429:
            raise AppError(
                "rate_limited",
                "API-Tennis quota exceeded",
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
            raise AppError("provider_unavailable", "API-Tennis request failed", 503)

        try:
            return response.json()
        except ValueError as error:
            raise AppError(
                "provider_unavailable",
                "API-Tennis response was not valid JSON",
                503,
            ) from error

    def _validate(self, model: type, payload: Any) -> Any:
        try:
            parsed = model.model_validate(payload)
        except ValidationError as error:
            raise AppError(
                "provider_unavailable",
                "API-Tennis response validation failed",
                503,
            ) from error
        if isinstance(parsed, ApiTennisResponse):
            if parsed.success != 1:
                raise AppError(
                    "provider_unavailable",
                    "API-Tennis reported an unsuccessful response",
                    503,
                )
            return parsed
        return parsed

    async def _match_rows(self, method: str, params: dict[str, Any]) -> list[MatchDto]:
        payload = await self._request(method, params)
        parsed = self._validate(ApiTennisResponse[list[MatchDto]], payload)
        return list(parsed.result or [])

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
        params: dict[str, Any] = {"timezone": "GMT"}
        if player_id is not None:
            external_id = await self._identities.external_id(
                "player", PROVIDER_NAME, player_id
            )
            if external_id is None:
                return []
            params["player_key"] = external_id
        rows = await self._match_rows("get_livescore", params)
        mapped = [
            match
            for dto in rows
            if (match := await map_match(dto, self._identities, self._now)) is not None
        ]
        return self._filter(mapped, player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        params = self._window_params(UPCOMING_WINDOW_DAYS)
        if player_id is not None:
            external_id = await self._identities.external_id(
                "player", PROVIDER_NAME, player_id
            )
            if external_id is None:
                return []
            params["player_key"] = external_id
        rows = await self._match_rows("get_fixtures", params)
        mapped = [
            match
            for dto in rows
            if (match := await map_match(dto, self._identities, self._now)) is not None
        ]
        scheduled = [match for match in mapped if match.status is MatchStatus.SCHEDULED]
        return self._filter(scheduled, player_id)

    def _window_params(self, days_ahead: int, *, days_back: int = 0) -> dict[str, Any]:
        today = self._now().astimezone(timezone.utc).date()
        return {
            "timezone": "GMT",
            "date_start": (today - timedelta(days=days_back)).isoformat(),
            "date_stop": (today + timedelta(days=days_ahead)).isoformat(),
        }

    async def search_players(self, query: str) -> list[Player]:
        normalized = query.strip().casefold()
        if not normalized:
            return []
        live_rows = await self._match_rows("get_livescore", {"timezone": "GMT"})
        fixture_rows = await self._match_rows(
            "get_fixtures", self._window_params(SEARCH_WINDOW_DAYS)
        )
        matches = [
            match
            for dto in [*live_rows, *fixture_rows]
            if (match := await map_match(dto, self._identities, self._now)) is not None
        ]
        seen: set[str] = set()
        results: list[Player] = []
        for match in matches:
            for player in match.players:
                if player.id in seen:
                    continue
                if normalized in player.name.casefold():
                    seen.add(player.id)
                    results.append(player)
        return results[:SEARCH_RESULT_LIMIT]

    async def get_player(self, player_id: str) -> Player:
        external_id = await self._identities.external_id(
            "player", PROVIDER_NAME, player_id
        )
        if external_id is None:
            raise AppError("not_found", "Player not found", 404)
        payload = await self._request("get_players", {"player_key": external_id})
        parsed = self._validate(ApiTennisResponse[list[PlayerDto]], payload)
        rows = parsed.result or []
        if not rows:
            raise AppError("not_found", "Player not found", 404)
        dto = rows[0]
        return Player(
            id=player_id,
            name=(dto.player_full_name or dto.player_name or "").strip()
            or "Unknown player",
            country_code=None,
            ranking=_latest_ranking(dto),
        )

    async def get_match(self, match_id: str) -> Match:
        external_id = await self._identities.external_id(
            "match", PROVIDER_NAME, match_id
        )
        if external_id is None:
            raise AppError("not_found", "Match not found", 404)
        rows = await self._match_rows(
            "get_fixtures", {"timezone": "GMT", "match_key": external_id}
        )
        if not rows:
            rows = await self._match_rows(
                "get_livescore", {"timezone": "GMT", "match_key": external_id}
            )
        if not rows:
            raise AppError("not_found", "Match not found", 404)
        match = await map_match(rows[0], self._identities, self._now)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        external_id = await self._identities.external_id(
            "match", PROVIDER_NAME, match_id
        )
        if external_id is None:
            raise AppError("not_found", "Match not found", 404)
        rows = await self._match_rows(
            "get_fixtures", {"timezone": "GMT", "match_key": external_id}
        )
        if not rows:
            rows = await self._match_rows(
                "get_livescore", {"timezone": "GMT", "match_key": external_id}
            )
        if not rows:
            raise AppError("not_found", "Match not found", 404)
        snapshot = await map_livescore_row_to_snapshot(rows[0], self._identities, self._now)
        if snapshot is None:
            raise AppError("not_found", "Match not found", 404)
        return snapshot

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        external_id = await self._identities.external_id(
            "player", PROVIDER_NAME, player_id
        )
        if external_id is None:
            raise AppError("not_found", "Player not found", 404)
        params = self._window_params(0, days_back=RECENT_RESULTS_WINDOW_DAYS)
        params["player_key"] = external_id
        rows = await self._match_rows("get_fixtures", params)
        mapped = [
            match
            for dto in rows
            if (match := await map_match(dto, self._identities, self._now)) is not None
        ]
        finished = [match for match in mapped if match.status is MatchStatus.FINISHED]
        finished.sort(
            key=lambda match: (
                match.scheduled_at or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        return finished[: max(1, min(limit, 10))]

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        first_external = await self._identities.external_id(
            "player", PROVIDER_NAME, first_player_id
        )
        second_external = await self._identities.external_id(
            "player", PROVIDER_NAME, second_player_id
        )
        if first_external is None or second_external is None:
            raise AppError("not_found", "Player not found", 404)
        payload = await self._request(
            "get_H2H",
            {
                "first_player_key": first_external,
                "second_player_key": second_external,
            },
        )
        parsed = self._validate(ApiTennisResponse[HeadToHeadDto], payload)
        dto = parsed.result or HeadToHeadDto.model_validate(
            {"H2H": [], "firstPlayerResults": [], "secondPlayerResults": []}
        )
        bounded = max(1, min(limit, 10))
        meetings = [
            match
            for row in dto.h2h[:bounded]
            if (match := await map_match(row, self._identities, self._now)) is not None
        ]
        first_recent = [
            match
            for row in dto.first_player_results[:bounded]
            if (match := await map_match(row, self._identities, self._now)) is not None
        ]
        second_recent = [
            match
            for row in dto.second_player_results[:bounded]
            if (match := await map_match(row, self._identities, self._now)) is not None
        ]
        return HeadToHead(
            first_player_id=first_player_id,
            second_player_id=second_player_id,
            meetings=tuple(meetings),
            first_player_recent=tuple(first_recent),
            second_player_recent=tuple(second_recent),
            freshness=DataFreshness(provider=PROVIDER_NAME, observed_at=self._now()),
        )

    async def get_score(self, match_id: str) -> LiveMatchState:
        match = await self.get_match(match_id)
        if match.live_state is None:
            raise AppError("not_found", "Score not available", 404)
        return match.live_state


def _latest_ranking(dto: PlayerDto) -> int | None:
    numeric_seasons = [
        stat for stat in dto.stats if (stat.season or "").strip().isdigit()
    ]
    if not numeric_seasons:
        return None
    latest = max(stat.season.strip() for stat in numeric_seasons)
    for stat in numeric_seasons:
        if stat.season.strip() == latest and (stat.rank or "").strip().isdigit():
            return int(stat.rank.strip())
    return None
