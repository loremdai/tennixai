"""API-Tennis REST adapter contract tests (deterministic, MockTransport only)."""

import json
from datetime import date, datetime, timezone
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
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.sync import PlayerDirectorySync
from app.providers.api_tennis import (
    ApiTennisProvider,
    STAT_NAME_MAP,
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
    if method == "get_standings":
        return httpx.Response(
            200,
            json={
                "success": 1,
                "result": [
                    {
                        "place": 1222,
                        "player": "Jie Cui",
                        "player_key": 1274,
                        "league": "ATP",
                        "movement": "0",
                        "country": "China",
                        "points": "150",
                    },
                    {
                        "place": 900,
                        "player": "F. Sun",
                        "player_key": 876,
                        "league": "ATP",
                        "movement": "0",
                        "country": "China",
                        "points": "200",
                    },
                    {
                        "place": 500,
                        "player": "M. Moeller",
                        "player_key": 4444,
                        "league": "ATP",
                        "movement": "0",
                        "country": "Germany",
                        "points": "300",
                    },
                ],
            },
        )
    return httpx.Response(404, json={"error": "1"})


def build_provider(handler=route_handler, *, with_directory: bool = True):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(wrapped), base_url=BASE_URL, timeout=10.0
    )
    directory = MemoryPlayerDirectoryRepository() if with_directory else None
    provider = ApiTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key=API_KEY,
        now=lambda: NOW,
        directory=directory,
    )
    return provider, seen, client, directory


def draw_unavailable_handler(request: httpx.Request) -> httpx.Response:
    if request.url.params.get("method") == "get_draw":
        return httpx.Response(403, json={"success": 0, "error": "not available"})
    return route_handler(request)


def test_metadata_normalizers_map_country_names_and_leave_unknown_values_unmapped() -> None:
    assert normalize_surface(" Red Clay ") == "clay"
    assert normalize_surface("Indoor Hard") is None
    assert country_code_from_name("Germany") == "deu"
    assert country_code_from_name("World") == "world"
    assert country_code_from_name("Russia") == "rus"
    assert country_code_from_name("Belarus") == "blr"
    assert country_code_from_name("Cyprus") == "cyp"
    assert country_code_from_name("Congo, the Democratic Republic of the") == "cod"
    assert country_code_from_name("Tennixia") is None


@pytest.mark.asyncio
async def test_finished_result_keeps_set_count_when_vendor_has_no_set_rows(provider) -> None:
    built, _ = provider
    row = dict(load("fixtures.json")["result"][0])
    row.update(
        {
            "event_final_result": "2 - 0",
            "event_status": "Finished",
            "event_winner": "First Player",
            "scores": [],
        }
    )

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.score is not None
    assert snapshot.match.live_state.score.sets_won == (2, 0)
    assert snapshot.match.live_state.score.sets == ()


@pytest.fixture()
async def provider():
    built, seen, client, directory = build_provider()
    sync = PlayerDirectorySync(built, directory, now=lambda: NOW)
    await sync.sync_rankings()
    await sync.sync_known_player_aliases()
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "circuit", "tour"),
    [("Atp Singles", CircuitTier.ATP, "atp"), ("Wta Singles", CircuitTier.WTA, "wta")],
)
async def test_match_mapping_preserves_recognized_tour_identity(
    provider, event_type, circuit, tour
) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["event_type_type"] = event_type

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.tournament.circuit is circuit
    assert snapshot.match.tournament.tour == tour


@pytest.mark.asyncio
async def test_blank_provider_round_maps_to_unavailable_value(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["tournament_round"] = "  "

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.round is None


@pytest.mark.asyncio
async def test_unknown_server_and_missing_tournament_metadata_stay_explicit(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row.update(
        {
            "event_serve": "Court Official",
            "tournament_key": None,
            "tournament_name": "  ",
        }
    )
    row["pointbypoint"][0]["player_served"] = "Court Official"

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.server_player_id is None
    assert snapshot.points[0].server_player_id is None
    assert snapshot.match.tournament.name == "Unknown tournament"
    assert snapshot.match.tournament.id == await built._identities.get_or_create(
        "tournament", "api_tennis", str(row["event_key"])
    )


@pytest.mark.asyncio
async def test_invalid_set_numbers_fall_back_to_response_order(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["scores"] = [
        {"score_set": "0", "score_first": "6", "score_second": "4"},
        {"score_set": "unknown", "score_first": "2", "score_second": "6"},
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    score = snapshot.match.live_state.score
    assert score is not None
    assert [set_score.number for set_score in score.sets] == [1, 2]


@pytest.mark.asyncio
async def test_set_game_scores_trim_whitespace_and_reject_negative_values(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["scores"] = [
        {"score_set": "1", "score_first": " 6 ", "score_second": "-1"}
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    score = snapshot.match.live_state.score
    assert score is not None
    assert score.sets[0].player1_games == 6
    assert score.sets[0].player2_games is None


@pytest.mark.asyncio
async def test_set_scores_decode_tiebreak_points_without_losing_set_order(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["scores"] = [
        {"score_set": "2", "score_first": "6.7", "score_second": "7.9"},
        {"score_set": "1", "score_first": "7.7", "score_second": "6.2"},
        {"score_set": "3", "score_first": "6", "score_second": "4"},
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    score = snapshot.match.live_state.score
    assert score is not None
    assert [
        (item.number, item.player1_games, item.player2_games)
        for item in score.sets
    ] == [(2, 6, 7), (1, 7, 6), (3, 6, 4)]
    assert [
        (item.player1_tiebreak_points, item.player2_tiebreak_points)
        for item in score.sets
    ] == [(7, 9), (7, 2), (None, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["-", "", " ", "-1", "6.x", "6.7.9", "6."])
async def test_invalid_dotted_set_score_stays_unknown(provider, invalid: str) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["scores"] = [
        {"score_set": "1", "score_first": invalid, "score_second": "7.8"}
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    score = snapshot.match.live_state.score
    assert score is not None
    assert score.sets[0].player1_games is None
    assert score.sets[0].player2_games == 7
    assert score.sets[0].player1_tiebreak_points is None
    assert score.sets[0].player2_tiebreak_points == 8


@pytest.mark.asyncio
async def test_missing_game_numbers_restart_at_one_for_each_set(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["pointbypoint"] = [
        {
            "set_number": "Set 1",
            "number_game": None,
            "points": [{"number_point": "1", "score": "15 - 0"}],
        },
        {
            "set_number": "Set 2",
            "number_game": None,
            "points": [{"number_point": "1", "score": "15 - 0"}],
        },
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert [(point.set_number, point.game_number) for point in snapshot.points] == [
        (1, 1),
        (2, 1),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_number", ["0", "-1"])
async def test_nonpositive_pbp_numbers_fall_back_to_positive_sequence_values(
    provider, invalid_number: str
) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["pointbypoint"] = [
        {
            "set_number": f"Set {invalid_number}",
            "number_game": invalid_number,
            "points": [{"number_point": invalid_number, "score": "15 - 0"}],
        }
    ]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    point = snapshot.points[0]
    assert (point.set_number, point.game_number, point.point_number) == (1, 1, 1)


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

    request = seen[-1]
    assert request.method == "GET"
    assert request.url.params["method"] == "get_livescore"
    assert request.url.params["timezone"] == "GMT"
    assert request.url.params["APIkey"] == API_KEY


@pytest.mark.asyncio
async def test_player_results_period_uses_beijing_calendar_at_year_boundaries() -> None:
    rows = []
    for event_key, event_date, event_time in (
        (1, "2025-12-31", "15:59"),  # Beijing Dec 31, outside 2026
        (2, "2025-12-31", "16:00"),  # Beijing Jan 1, inside 2026
        (3, "2026-12-31", "15:59"),  # Beijing Dec 31, inside 2026
        (4, "2026-12-31", "16:00"),  # Beijing Jan 1, outside 2026
        (5, "2026-07-01", None),  # Date-only row remains visible for review
    ):
        rows.append(
            {
                "event_key": event_key,
                "event_date": event_date,
                "event_time": event_time,
                "event_first_player": "A. Player",
                "first_player_key": 1274,
                "event_second_player": "B. Player",
                "second_player_key": 876,
                "event_winner": "First Player",
                "event_status": "Finished",
                "event_type_type": "Atp Singles",
                "tournament_name": "Boundary Open",
                "tournament_key": 2356,
            }
        )

    def history_handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("method") == "get_fixtures":
            date_start = request.url.params["date_start"]
            date_stop = request.url.params["date_stop"]
            matching_rows = [
                row for row in rows if date_start <= row["event_date"] <= date_stop
            ]
            return httpx.Response(200, json={"success": 1, "result": matching_rows})
        return route_handler(request)

    built, seen, client, _ = build_provider(history_handler, with_directory=False)
    try:
        player_id = await built._identities.get_or_create(
            "player", "api_tennis", "1274"
        )
        matches = await built.get_player_results_for_period(
            player_id, start=date(2026, 1, 1), end=date(2026, 12, 31)
        )

        assert {match.id for match in matches} == {
            await built._identities.get_or_create("match", "api_tennis", "2"),
            await built._identities.get_or_create("match", "api_tennis", "3"),
            await built._identities.get_or_create("match", "api_tennis", "5"),
        }
        request = seen[-1]
        assert request.url.params["timezone"] == "GMT"
        assert request.url.params["date_start"] == "2025-12-30"
        assert request.url.params["date_stop"] == "2027-01-01"
    finally:
        await client.aclose()


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
    assert state.current_set_number == 3
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
async def test_live_state_does_not_infer_current_set_from_score_rows(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["event_status"] = "In Progress"

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.current_set_number is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_status", "event_live"),
    [("Set 3", "1"), ("Cancelled", "0")],
)
async def test_non_finished_match_does_not_claim_event_winner(
    provider, event_status: str, event_live: str
) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["event_status"] = event_status
    row["event_live"] = event_live
    row["event_winner"] = "First Player"

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.winner_player_id is None


@pytest.mark.asyncio
async def test_missing_provider_tiebreak_marker_stays_unknown(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.score is not None
    assert snapshot.match.live_state.score.is_tiebreak is None


@pytest.mark.asyncio
async def test_missing_final_set_count_stays_unknown_in_match_and_pbp(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row["event_final_result"] = "-"

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.score is not None
    assert snapshot.match.live_state.score.sets_won is None
    assert snapshot.points
    assert snapshot.points[0].score_after.sets_won is None


@pytest.mark.asyncio
async def test_scheduled_zero_placeholders_do_not_create_a_live_score(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    row.update(
        {
            "event_status": "",
            "event_live": "0",
            "event_final_result": "0 - 0",
            "event_game_result": "0 - 0",
            "scores": [
                {"score_first": "0", "score_second": "0", "score_set": "1"}
            ],
            "pointbypoint": [],
        }
    )

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.match.status is MatchStatus.SCHEDULED
    assert snapshot.match.live_state is None


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
    assert first.score_before is not None
    assert first.score_before.points == ("0", "0")
    assert first.score_after.points == tuple(
        side.strip() for side in first_game["points"][0]["score"].split(" - ")
    )
    # The point score advanced from 0-0 on exactly one side, so the winner is
    # determinable and equals the side whose score changed.
    assert first.winner_player_id is not None
    assert first.quality is None
    assert first.is_break_point is None
    assert first.is_set_point is None
    assert first.is_match_point is None
    assert all(point.observed_at == NOW for point in snapshot.points)

    raw_breakpoint_sequences = {
        sequence
        for sequence, point in enumerate(
            (
                point
                for game in load("livescore.json")["result"][0]["pointbypoint"]
                for point in game.get("points") or []
            ),
            start=1,
        )
        if point.get("break_point")
    }
    assert raw_breakpoint_sequences
    assert all(
        point.is_break_point is None
        for point in snapshot.points
        if point.sequence in raw_breakpoint_sequences
    )

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
async def test_unrecognized_point_flag_text_remains_unknown(provider) -> None:
    built, _ = provider
    row = load("livescore.json")["result"][0]
    row["pointbypoint"][2]["points"][3]["break_point"] = "First Play"
    row["pointbypoint"][2]["points"][4]["set_point"] = "First Play"
    row["pointbypoint"][2]["points"][5]["match_point"] = "First Play"
    dto = MatchDto.model_validate(row)

    snapshot = await map_livescore_row_to_snapshot(dto, built._identities, built._now)

    assert snapshot is not None
    # API-Tennis documents these fields but does not define non-null values;
    # never turn opaque vendor text into a confirmed key-point badge.
    assert snapshot.points[15].is_break_point is None
    assert snapshot.points[16].is_set_point is None
    assert snapshot.points[17].is_match_point is None


@pytest.mark.asyncio
async def test_null_point_flags_remain_unknown(provider) -> None:
    built, _ = provider
    row = load("livescore.json")["result"][0]
    dto = MatchDto.model_validate(row)

    snapshot = await map_livescore_row_to_snapshot(dto, built._identities, built._now)

    assert snapshot is not None
    first = snapshot.points[0]
    assert first.is_break_point is None
    assert first.is_set_point is None
    assert first.is_match_point is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("advantage_score", "winner_index"),
    [("A - 40", 1), ("40 - A", 0)],
)
async def test_advantage_reset_assigns_point_to_player_who_removed_advantage(
    provider, advantage_score, winner_index: int
) -> None:
    built, _ = provider
    row = load("livescore.json")["result"][0]
    row["pointbypoint"] = [
        {
            "set_number": "Set 1",
            "number_game": "1",
            "player_served": "First Player",
            "points": [
                {"number_point": str(index), "score": score}
                for index, score in enumerate(
                    ("40 - 40", advantage_score, "40 - 40"), start=1
                )
            ],
        }
    ]
    dto = MatchDto.model_validate(row)

    snapshot = await map_livescore_row_to_snapshot(dto, built._identities, built._now)

    assert snapshot is not None
    assert snapshot.points[-1].winner_player_id == snapshot.match.players[winner_index].id


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
    raw_first_serve_points = next(
        stat
        for stat in rows["statistics"]
        if stat["stat_name"] == "1st serve points won"
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

    serve_points_won = next(
        statistic
        for statistic in snapshot.statistics
        if statistic.name is StatisticName.FIRST_SERVE_POINTS_WON
        and statistic.period == "match"
    )
    assert raw_first_serve_points["stat_value"] == "72%"
    assert raw_first_serve_points["stat_won"] == 26
    assert raw_first_serve_points["stat_total"] == 36
    assert serve_points_won.player1_value == 72.0
    assert serve_points_won.unit == "percent"


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
    quality = {item.capability: item for item in snapshot.quality}
    assert quality["point_by_point"].provider == "api_tennis"
    assert quality["point_by_point"].reason is None
    assert quality["point_by_point"].observed_at == NOW
    assert quality["momentum"].reason == "not_computed"

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
async def test_statistics_capability_is_partial_when_only_one_side_is_returned(
    provider,
) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    one_player_aces = next(
        stat for stat in row["statistics"] if stat["stat_name"] == "Aces"
    )
    row["statistics"] = [one_player_aces]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    metric = snapshot.statistics[0]
    assert metric.availability is CapabilityStatus.PARTIAL
    stats_quality = next(item for item in snapshot.quality if item.capability == "statistics")
    assert stats_quality.status is CapabilityStatus.PARTIAL


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stat_name", "invalid_value"),
    [
        ("Aces", "NaN"),
        ("Aces", "inf"),
        ("Aces", "-1"),
        ("1st serve percentage", "101%"),
    ],
)
async def test_invalid_stat_values_are_not_exposed(
    provider, stat_name: str, invalid_value: str
) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    source = next(stat for stat in row["statistics"] if stat["stat_name"] == stat_name)
    row["statistics"] = [source | {"stat_value": invalid_value}]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.statistics == ()
    stats_quality = next(item for item in snapshot.quality if item.capability == "statistics")
    assert stats_quality.status is CapabilityStatus.UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize("period", ["set 0", "set:-1", "other"])
async def test_invalid_stat_periods_are_not_exposed(provider, period: str) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    source = next(stat for stat in row["statistics"] if stat["stat_name"] == "Aces")
    row["statistics"] = [source | {"stat_period": period}]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.statistics == ()
    stats_quality = next(item for item in snapshot.quality if item.capability == "statistics")
    assert stats_quality.status is CapabilityStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_statistic_for_unknown_player_is_not_exposed(provider) -> None:
    built, _ = provider
    row = dict(load("livescore.json")["result"][0])
    source = next(stat for stat in row["statistics"] if stat["stat_name"] == "Aces")
    row["statistics"] = [source | {"player_key": "999999"}]

    snapshot = await map_livescore_row_to_snapshot(
        MatchDto.model_validate(row), built._identities, built._now
    )

    assert snapshot is not None
    assert snapshot.statistics == ()
    stats_quality = next(item for item in snapshot.quality if item.capability == "statistics")
    assert stats_quality.status is CapabilityStatus.UNAVAILABLE


def test_stat_catalog_covers_each_canonical_metric_with_its_unit() -> None:
    expected = {
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

    assert STAT_NAME_MAP == expected


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


@pytest.mark.parametrize(
    ("list_key", "match_field", "truncation_field"),
    [
        ("H2H", "meetings", "meetings_may_be_truncated"),
        (
            "firstPlayerResults",
            "first_player_recent",
            "first_player_recent_may_be_truncated",
        ),
        (
            "secondPlayerResults",
            "second_player_recent",
            "second_player_recent_may_be_truncated",
        ),
    ],
)
@pytest.mark.asyncio
async def test_head_to_head_reports_raw_cap_when_a_row_cannot_be_mapped(
    list_key: str, match_field: str, truncation_field: str
) -> None:
    rows = []
    for event_key in range(10):
        rows.append(
            {
                "event_key": event_key,
                "event_date": "2026-09-08",
                "event_time": "07:10",
                "event_first_player": "J. Cui",
                "first_player_key": 1274,
                "event_second_player": "F. Sun",
                "second_player_key": None if event_key == 0 else 876,
                "event_winner": "First Player",
                "event_status": "Finished",
                "event_type_type": "Atp Singles",
                "tournament_name": "Boundary Open",
                "tournament_key": 2356,
            }
        )

    def history_handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("method") == "get_H2H":
            return httpx.Response(
                200,
                json={
                    "success": 1,
                    "result": {
                        "H2H": rows if list_key == "H2H" else [],
                        "firstPlayerResults": (
                            rows if list_key == "firstPlayerResults" else []
                        ),
                        "secondPlayerResults": (
                            rows if list_key == "secondPlayerResults" else []
                        ),
                    },
                },
            )
        return route_handler(request)

    built, _, client, _ = build_provider(history_handler, with_directory=False)
    try:
        first_id = await built._identities.get_or_create(
            "player", "api_tennis", "1274"
        )
        second_id = await built._identities.get_or_create(
            "player", "api_tennis", "876"
        )

        result = await built.get_head_to_head(first_id, second_id, limit=10)

        assert len(getattr(result, match_field)) == 9
        assert getattr(result, truncation_field) is True
        assert all(
            getattr(result, field) is (field == truncation_field)
            for field in (
                "meetings_may_be_truncated",
                "first_player_recent_may_be_truncated",
                "second_player_recent_may_be_truncated",
            )
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_search_players_reads_local_directory_without_vendor_scan(
    provider,
) -> None:
    built, seen = provider
    seen.clear()

    results = await built.search_players("moeller")

    assert [player.name for player in results] == ["M. Moeller"]
    assert results[0].id.startswith("ply_")
    methods = [item.url.params.get("method") for item in seen]
    assert methods == []
    assert await built.search_players("nobody-here") == []
    assert await built.search_players("  ") == []


@pytest.mark.asyncio
async def test_search_players_without_directory_is_typed_unsupported() -> None:
    built, _seen, client, _directory = build_provider(with_directory=False)
    try:
        with pytest.raises(AppError) as error_info:
            await built.search_players("Cui")
        assert error_info.value.code == "unsupported"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_player_does_not_use_season_rank_as_current_ranking(provider) -> None:
    built, seen = provider

    cui = (await built.search_players("Cui"))[0]
    player = await built.get_player(cui.id)

    request = next(
        item for item in seen if item.url.params.get("method") == "get_players"
    )
    assert request.url.params["player_key"] == "1274"
    assert player.id == cui.id
    assert player.name == "Jie Cui"
    assert player.ranking is None
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
    built, seen, client, _directory = build_provider(draw_unavailable_handler)
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
        built, _, client, _directory = build_provider(
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

    built, _, client, _directory = build_provider(handler)
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

    built, _, client, _directory = build_provider(handler)
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
        built, _, client, _directory = build_provider(
            lambda request: httpx.Response(200, json=payload)
        )
        try:
            assert await built.get_live_matches() == []
            assert await built.get_fixtures() == []
        finally:
            await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_translates_to_provider_unavailable() -> None:
    built, _, client, _directory = build_provider(
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
