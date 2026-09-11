"""API-Tennis REST adapter contract tests (deterministic, MockTransport only)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.domain import (
    CapabilityStatus,
    CircuitTier,
    Discipline,
    Gender,
    MatchSnapshot,
    MatchStatus,
    StatisticName,
)
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.api_tennis import (
    ApiTennisProvider,
    country_code_from_name,
    map_livescore_row_to_snapshot,
    map_status,
    normalize_surface,
)
from app.providers.api_tennis_classification import classify_event_type
from app.providers.api_tennis_dtos import MatchDto

FIXTURES = Path(__file__).parent / "fixtures" / "api_tennis"
BASE_URL = "https://api.api-tennis.com/tennis/"
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
API_KEY = "test-key"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def route_handler(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    method = params.get("method")
    if method == "get_livescore":
        data = load("livescore.json")
        match_key = params.get("match_key")
        if match_key is not None:
            data = {
                "success": 1,
                "result": [
                    row
                    for row in data["result"]
                    if str(row["event_key"]) == match_key
                ],
            }
        return httpx.Response(200, json=data)
    if method == "get_fixtures":
        rows = load("fixtures.json")["result"]
        match_key = params.get("match_key")
        if match_key is not None:
            rows = [row for row in rows if str(row["event_key"]) == match_key]
        player_key = params.get("player_key")
        if player_key is not None:
            rows = [
                row
                for row in rows
                if str(row["first_player_key"]) == player_key
                or str(row["second_player_key"]) == player_key
            ]
        return httpx.Response(200, json={"success": 1, "result": rows})
    if method == "get_draw":
        return httpx.Response(
            200,
            json={
                "success": 1,
                "result": {
                    "tournament": {
                        "tournament_surface": "Hard",
                        "tournament_country": "Atp Singles",
                    },
                    "source": "draw_feed",
                    "brackets": [],
                },
            },
        )
    if method == "get_H2H":
        return httpx.Response(200, json=load("h2h.json"))
    if method == "get_players":
        if params.get("player_key") == "1274":
            return httpx.Response(200, json=load("players.json"))
        return httpx.Response(200, json={"success": 1, "result": []})
    if method == "get_events":
        return httpx.Response(200, json=load("events.json"))
    return httpx.Response(404, json={"error": "1"})


def build_provider(handler=route_handler):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(wrapped), base_url=BASE_URL, timeout=10.0
    )
    provider = ApiTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key=API_KEY,
        now=lambda: NOW,
    )
    return provider, seen, client


def draw_unavailable_handler(request: httpx.Request) -> httpx.Response:
    if request.url.params.get("method") == "get_draw":
        return httpx.Response(403, json={"success": 0, "error": "not available"})
    return route_handler(request)


def test_metadata_normalizers_only_map_explicit_values() -> None:
    assert normalize_surface(" Red Clay ") == "clay"
    assert normalize_surface("Indoor Hard") is None
    assert country_code_from_name("Germany") == "deu"
    assert country_code_from_name("World") is None


@pytest.fixture()
async def provider():
    built, seen, client = build_provider()
    try:
        yield built, seen
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("event_type", "circuit", "gender", "discipline"),
    [
        ("Atp Singles", "atp", "men", "singles"),
        ("Wta Doubles", "wta", "women", "doubles"),
        ("Challenger Men Singles", "challenger", "men", "singles"),
        ("Itf Women Doubles", "itf", "women", "doubles"),
        ("Challenger Women Doubles", "challenger", "women", "doubles"),
        ("Itf Men Singles", "itf", "men", "singles"),
        ("Mixed Doubles", "other", "mixed", "doubles"),
        ("Boys Singles", "other", "unknown", "singles"),
        ("Girls Doubles", "other", "unknown", "doubles"),
        ("Exhibition Men", "other", "men", "unknown"),
        ("Exhibition Mixed Doubles", "other", "mixed", "doubles"),
        ("Teams Women", "other", "women", "team"),
        ("Teams Mix", "other", "mixed", "team"),
        ("Something Weird", "other", "unknown", "unknown"),
        ("", "other", "unknown", "unknown"),
    ],
)
def test_classifies_reliable_event_types(event_type, circuit, gender, discipline):
    assert classify_event_type(event_type) == (
        CircuitTier(circuit),
        Gender(gender),
        Discipline(discipline),
    )


def test_classification_of_none_is_honest_unknown():
    assert classify_event_type(None) == (
        CircuitTier.OTHER,
        Gender.UNKNOWN,
        Discipline.UNKNOWN,
    )


@pytest.mark.parametrize(
    ("event_status", "event_live", "expected"),
    [
        (None, "1", MatchStatus.LIVE),
        ("", "1", MatchStatus.LIVE),
        ("Finished", "1", MatchStatus.FINISHED),
        ("Set 1", "0", MatchStatus.LIVE),
    ],
)
def test_event_live_flag_fills_missing_live_status_but_terminal_wins(
    event_status, event_live, expected
) -> None:
    assert map_status(event_status, event_live) is expected


@pytest.mark.asyncio
async def test_live_request_uses_method_timezone_and_key(provider) -> None:
    built, seen = provider

    await built.get_live_matches()

    request = seen[0]
    assert request.method == "GET"
    assert request.url.params["method"] == "get_livescore"
    assert request.url.params["timezone"] == "GMT"
    assert request.url.params["APIkey"] == API_KEY


@pytest.mark.asyncio
async def test_live_maps_vendor_payload_to_canonical(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()

    assert len(live) == 2
    assert all(match.status is MatchStatus.LIVE for match in live)
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    assert rich.id.startswith("mat_")
    assert rich.status is MatchStatus.LIVE
    assert rich.scheduled_at == datetime(2026, 9, 9, 9, 45, tzinfo=timezone.utc)
    assert [player.name for player in rich.players] == ["M. Moeller", "M. Soto"]
    assert all(player.id.startswith("ply_") for player in rich.players)
    assert rich.tournament.id.startswith("trn_")
    assert rich.tournament.name == "Tulln"
    assert rich.tournament.circuit is CircuitTier.CHALLENGER
    assert rich.tournament.gender is Gender.MEN
    assert rich.tournament.discipline is Discipline.SINGLES

    state = rich.live_state
    assert state is not None and state.score is not None
    assert state.score.sets_won == (1, 1)
    assert [
        (row.number, row.player1_games, row.player2_games) for row in state.score.sets
    ] == [(1, 4, 6), (2, 6, 3)]
    assert state.score.points == ("0", "40")
    assert state.server_player_id == rich.players[0].id
    assert rich.winner_player_id is None

    assert rich.freshness.provider == "api_tennis"
    assert rich.freshness.observed_at == NOW
    assert rich.freshness.source_updated_at is None


@pytest.mark.asyncio
async def test_vendor_fields_never_leak_into_canonical_output(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    dumped = "".join(match.model_dump_json() for match in live)

    for token in [
        "event_key",
        "event_first_player",
        "first_player_key",
        "pointbypoint",
        "stat_name",
        "stat_value",
        "future_additive_field",
        "12161239",
        "7349",
    ]:
        assert token not in dumped


@pytest.mark.asyncio
async def test_snapshot_maps_points_with_sequence_flags_and_winner_rules(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    snapshot = await built.get_match_snapshot(rich.id)

    assert isinstance(snapshot, MatchSnapshot)
    assert snapshot.match.id == rich.id
    assert snapshot.state_version == 0
    assert snapshot.as_of == NOW

    fixture_games = load("livescore.json")["result"][0]["pointbypoint"]
    fixture_points = [
        point for game in fixture_games for point in game.get("points") or []
    ]
    assert len(snapshot.points) == len(fixture_points)
    assert [point.sequence for point in snapshot.points] == list(
        range(1, len(snapshot.points) + 1)
    )

    first_game = fixture_games[0]
    expected_server = (
        rich.players[0]
        if first_game["player_served"] == "First Player"
        else rich.players[1]
    )
    first = snapshot.points[0]
    assert first.set_number == 1
    assert first.game_number == 1
    assert first.point_number == 1
    assert first.server_player_id == expected_server.id
    assert first.score_after.points == tuple(
        side.strip() for side in first_game["points"][0]["score"].split(" - ")
    )
    # The point score advanced from 0-0 on exactly one side, so the winner is
    # determinable and equals the side whose score changed.
    assert first.winner_player_id is not None
    assert first.quality is None

    flagged = [point for point in snapshot.points if point.is_break_point]
    raw_flagged_count = sum(
        1
        for game in load("livescore.json")["result"][0]["pointbypoint"]
        for point in game.get("points") or []
        if point.get("break_point")
    )
    assert flagged
    assert len(flagged) == raw_flagged_count

    indeterminate = [point for point in snapshot.points if point.winner_player_id is None]
    assert indeterminate, "fixture must contain an indeterminate point"
    quality = indeterminate[0].quality
    assert quality is not None
    assert quality.status is CapabilityStatus.PARTIAL
    assert quality.reason == "winner_indeterminate"
    assert quality.provider == "api_tennis"

    assert all(point.match_id == rich.id for point in snapshot.points)
    assert all(point.provider == "api_tennis" for point in snapshot.points)
    assert all(point.revision == 1 for point in snapshot.points)
    assert len({point.source_fingerprint for point in snapshot.points}) == len(
        snapshot.points
    )
    point_identities = {
        (point.set_number, point.game_number, point.point_number)
        for point in snapshot.points
    }
    assert len(point_identities) == len(snapshot.points)


@pytest.mark.asyncio
async def test_snapshot_normalizes_duplicate_vendor_point_numbers(provider) -> None:
    built, _ = provider
    row = load("livescore.json")["result"][0]
    row["pointbypoint"][0]["points"][1]["number_point"] = row["pointbypoint"][0]["points"][0]["number_point"]
    dto = MatchDto.model_validate(row)

    snapshot = await map_livescore_row_to_snapshot(dto, built._identities, built._now)

    assert snapshot is not None
    identities = [
        (point.set_number, point.game_number, point.point_number)
        for point in snapshot.points
    ]
    assert len(identities) == len(set(identities))


@pytest.mark.asyncio
async def test_snapshot_maps_22_stat_catalog_and_ignores_unmappable(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    snapshot = await built.get_match_snapshot(rich.id)

    rows = load("livescore.json")["result"][0]
    p1_key = str(rows["first_player_key"])
    raw_aces = next(
        stat
        for stat in rows["statistics"]
        if stat["stat_name"] == "Aces"
        and stat["stat_period"] == "match"
        and str(stat["player_key"]) == p1_key
    )

    names = {(statistic.name, statistic.period) for statistic in snapshot.statistics}
    assert (StatisticName.ACES, "match") in names
    assert (StatisticName.FIRST_SERVE_PERCENTAGE, "set:1") in names
    assert all(
        statistic.name in StatisticName for statistic in snapshot.statistics
    )
    # One merged row per (name, period); "Last 10 balls" and unknown names dropped.
    assert len(snapshot.statistics) == len(names)
    assert all(
        statistic.name.value != "last_10_balls" for statistic in snapshot.statistics
    )
    raw_pairs = {
        (stat["stat_name"], stat["stat_period"]) for stat in rows["statistics"]
    }
    assert ("Last 10 balls", "match") in raw_pairs  # present in vendor data, dropped
    assert ("Future Metric", "match") in raw_pairs  # unknown name, dropped
    assert len(names) == len(raw_pairs) - 2

    aces = next(
        statistic
        for statistic in snapshot.statistics
        if statistic.name is StatisticName.ACES and statistic.period == "match"
    )
    assert aces.player1_value == float(raw_aces["stat_value"])
    assert aces.unit == "count"
    assert aces.availability is CapabilityStatus.AVAILABLE
    assert aces.provenance.value == "provider"
    assert aces.as_of == NOW
    assert aces.match_id == rich.id

    percentage = next(
        statistic
        for statistic in snapshot.statistics
        if statistic.name is StatisticName.FIRST_SERVE_PERCENTAGE
        and statistic.period == "match"
    )
    assert percentage.unit == "percent"
    assert percentage.player1_value is not None
    assert percentage.player2_value is not None


@pytest.mark.asyncio
async def test_snapshot_quality_declares_available_and_missing_capabilities(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    snapshot = await built.get_match_snapshot(rich.id)

    declared = {item.capability: item.status for item in snapshot.quality}
    assert declared["point_by_point"] is CapabilityStatus.AVAILABLE
    assert declared["statistics"] is CapabilityStatus.AVAILABLE
    assert declared["momentum"] is CapabilityStatus.UNAVAILABLE

    # The ITF match has an empty statistics array: declared, not zero.
    itf = next(
        match
        for match in live
        if match.tournament.name.startswith("M15 Hurghada")
    )
    itf_snapshot = await built.get_match_snapshot(itf.id)
    itf_declared = {item.capability: item.status for item in itf_snapshot.quality}
    assert itf_declared["statistics"] is CapabilityStatus.UNAVAILABLE
    assert itf_snapshot.statistics == ()
    assert itf_declared["point_by_point"] is CapabilityStatus.AVAILABLE
    assert itf_snapshot.points


@pytest.mark.asyncio
async def test_snapshot_of_upcoming_match_is_version_zero_with_declared_gaps(provider) -> None:
    built, _ = provider

    fixtures = await built.get_fixtures()
    assert len(fixtures) == 1
    upcoming = fixtures[0]
    assert upcoming.status is MatchStatus.SCHEDULED
    assert upcoming.live_state is None
    assert upcoming.tournament.circuit is CircuitTier.CHALLENGER
    assert upcoming.tournament.discipline is Discipline.DOUBLES

    snapshot = await built.get_match_snapshot(upcoming.id)
    assert snapshot.state_version == 0
    assert snapshot.points == ()
    assert snapshot.statistics == ()
    declared = {item.capability: item.status for item in snapshot.quality}
    assert declared["point_by_point"] is CapabilityStatus.UNAVAILABLE
    assert declared["statistics"] is CapabilityStatus.UNAVAILABLE
    assert declared["momentum"] is CapabilityStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_fixtures_request_uses_bounded_window_and_keeps_only_scheduled(provider) -> None:
    built, seen = provider

    fixtures = await built.get_fixtures()

    request = next(
        item for item in seen if item.url.params.get("method") == "get_fixtures"
    )
    assert request.url.params["date_start"] == "2026-09-09"
    assert request.url.params["date_stop"] == "2026-09-16"
    assert request.url.params["timezone"] == "GMT"
    assert [match.status for match in fixtures] == [MatchStatus.SCHEDULED]


@pytest.mark.asyncio
async def test_fixtures_player_filter_sends_provider_external_key(provider) -> None:
    built, seen = provider

    players = await built.search_players("Cui")
    cui = players[0]

    await built.get_fixtures(player_id=cui.id)

    request = next(
        item
        for item in seen
        if item.url.params.get("method") == "get_fixtures"
        and item.url.params.get("player_key") is not None
    )
    assert request.url.params["player_key"] == "1274"


@pytest.mark.asyncio
async def test_get_recent_results_uses_player_window_and_terminal_filter(provider) -> None:
    built, seen = provider

    players = await built.search_players("Cui")
    cui = players[0]

    results = await built.get_recent_results(cui.id, limit=2)

    request = next(
        item
        for item in seen
        if item.url.params.get("method") == "get_fixtures"
        and item.url.params.get("player_key") == "1274"
        and item.url.params.get("date_start") == "2026-08-10"
    )
    assert request.url.params["date_stop"] == "2026-09-09"
    assert len(results) == 1
    assert results[0].status is MatchStatus.FINISHED
    assert results[0].winner_player_id == results[0].players[0].id

    with pytest.raises(AppError) as error_info:
        await built.get_recent_results("ply_missing", limit=2)
    assert error_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_head_to_head_maps_meetings_and_recent_with_limits(provider) -> None:
    built, seen = provider

    cui = (await built.search_players("Cui"))[0]
    sun = (await built.search_players("F. Sun"))[0]

    head_to_head = await built.get_head_to_head(cui.id, sun.id, limit=2)

    request = next(
        item for item in seen if item.url.params.get("method") == "get_H2H"
    )
    assert request.url.params["first_player_key"] == "1274"
    assert request.url.params["second_player_key"] == "876"
    assert head_to_head.first_player_id == cui.id
    assert head_to_head.second_player_id == sun.id
    assert len(head_to_head.meetings) == 2
    assert len(head_to_head.first_player_recent) == 2
    assert len(head_to_head.second_player_recent) == 2
    assert head_to_head.meetings[0].status is MatchStatus.FINISHED
    assert head_to_head.freshness.provider == "api_tennis"

    with pytest.raises(AppError):
        await built.get_head_to_head(cui.id, "ply_missing", limit=2)


@pytest.mark.asyncio
async def test_search_players_scans_live_and_upcoming_windows(provider) -> None:
    built, seen = provider

    results = await built.search_players("moeller")

    assert [player.name for player in results] == ["M. Moeller"]
    assert results[0].id.startswith("ply_")
    methods = [item.url.params.get("method") for item in seen]
    assert "get_livescore" in methods
    fixture_request = next(
        item for item in seen if item.url.params.get("method") == "get_fixtures"
    )
    assert fixture_request.url.params["date_start"] == "2026-09-09"
    assert fixture_request.url.params["date_stop"] == "2026-09-12"

    assert await built.search_players("nobody-here") == []
    assert await built.search_players("  ") == []


@pytest.mark.asyncio
async def test_get_player_maps_profile_with_latest_season_ranking(provider) -> None:
    built, seen = provider

    cui = (await built.search_players("Cui"))[0]
    player = await built.get_player(cui.id)

    request = next(
        item for item in seen if item.url.params.get("method") == "get_players"
    )
    assert request.url.params["player_key"] == "1274"
    assert player.id == cui.id
    assert player.name == "Jie Cui"
    assert player.ranking == 1222
    assert player.country_code == "chn"

    with pytest.raises(AppError) as error_info:
        await built.get_player("ply_missing")
    assert error_info.value.code == "not_found"
    calls_before = len(seen)
    with pytest.raises(AppError):
        await built.get_player("ply_missing")
    assert len(seen) == calls_before  # no network for unmapped ids


@pytest.mark.asyncio
async def test_get_match_falls_back_from_fixtures_to_livescore(provider) -> None:
    built, seen = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    seen.clear()

    detail = await built.get_match(rich.id)

    methods = [item.url.params.get("method") for item in seen]
    assert methods == ["get_fixtures", "get_livescore", "get_draw"]
    assert seen[0].url.params["match_key"] == "12161239"
    assert detail.id == rich.id
    assert detail.status is MatchStatus.LIVE

    with pytest.raises(AppError) as error_info:
        await built.get_match("mat_missing")
    assert error_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_match_snapshot_enriches_surface_from_official_draw_metadata(provider) -> None:
    built, seen = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    seen.clear()

    snapshot = await built.get_match_snapshot(rich.id)

    draw_request = next(
        item for item in seen if item.url.params.get("method") == "get_draw"
    )
    assert draw_request.url.params["tournament_key"] == "4579"
    assert draw_request.url.params["tournament_season"] == "2026"
    assert snapshot.match.surface == "hard"


@pytest.mark.asyncio
async def test_match_snapshot_keeps_match_when_draw_metadata_is_unavailable() -> None:
    built, seen, client = build_provider(draw_unavailable_handler)
    try:
        live = await built.get_live_matches()
        rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
        seen.clear()

        snapshot = await built.get_match_snapshot(rich.id)

        assert snapshot.match.status is MatchStatus.LIVE
        assert snapshot.match.surface is None
        assert any(
            item.url.params.get("method") == "get_draw" for item in seen
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_score_returns_live_state_or_not_found(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    rich = next(match for match in live if match.round == "Tulln - 1/8-finals")
    state = await built.get_score(rich.id)
    assert state.score is not None
    assert state.server_player_id == rich.players[0].id

    fixtures = await built.get_fixtures()
    with pytest.raises(AppError) as error_info:
        await built.get_score(fixtures[0].id)
    assert error_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_success_zero_and_error_payloads_translate_to_provider_unavailable() -> None:
    for payload in (
        {"success": 0},
        {"error": "1", "result": [{"param": "player_key", "msg": "Required", "cod": 201}]},
    ):
        built, _, client = build_provider(
            lambda request: httpx.Response(200, json=payload)
        )
        try:
            with pytest.raises(AppError) as error_info:
                await built.get_live_matches()
        finally:
            await client.aclose()
        assert error_info.value.code == "provider_unavailable"
        assert error_info.value.status_code == 503


@pytest.mark.parametrize(
    ("status_code", "expected_code", "expected_status"),
    [
        (404, "not_found", 404),
        (429, "rate_limited", 429),
        (403, "provider_unavailable", 503),
        (500, "provider_unavailable", 503),
    ],
)
@pytest.mark.asyncio
async def test_http_errors_translate_to_typed_app_errors(
    status_code: int, expected_code: str, expected_status: int
) -> None:
    headers = {"Retry-After": "30"} if status_code == 429 else {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "boom"}, headers=headers)

    built, _, client = build_provider(handler)
    try:
        with pytest.raises(AppError) as error_info:
            await built.get_live_matches()
    finally:
        await client.aclose()

    error = error_info.value
    assert error.code == expected_code
    assert error.status_code == expected_status
    if status_code == 429:
        assert error.details["retry_after"] == "30"
    assert API_KEY not in error.message
    assert API_KEY not in str(error)
    assert "APIkey" not in error.message


@pytest.mark.asyncio
async def test_network_failure_translates_without_leaking_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    built, _, client = build_provider(handler)
    try:
        with pytest.raises(AppError) as error_info:
            await built.get_live_matches()
    finally:
        await client.aclose()

    error = error_info.value
    assert error.code == "provider_unavailable"
    assert API_KEY not in error.message
    assert API_KEY not in str(error.details)


@pytest.mark.asyncio
async def test_empty_and_missing_results_are_honest_empty_lists() -> None:
    for payload in ({"success": 1, "result": []}, {"success": 1}):
        built, _, client = build_provider(
            lambda request: httpx.Response(200, json=payload)
        )
        try:
            assert await built.get_live_matches() == []
            assert await built.get_fixtures() == []
        finally:
            await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_translates_to_provider_unavailable() -> None:
    built, _, client = build_provider(
        lambda request: httpx.Response(200, text="<html>quota page</html>")
    )
    try:
        with pytest.raises(AppError) as error_info:
            await built.get_live_matches()
    finally:
        await client.aclose()
    assert error_info.value.code == "provider_unavailable"


@pytest.mark.asyncio
async def test_internal_ids_are_stable_and_reversible_across_calls(provider) -> None:
    built, _ = provider

    first = await built.get_live_matches()
    second = await built.get_live_matches()

    assert [match.id for match in first] == [match.id for match in second]
    assert all("12161239" not in match.id for match in first)
