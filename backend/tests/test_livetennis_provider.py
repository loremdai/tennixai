import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.domain import MatchStatus
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.livetennis import LiveTennisProvider

FIXTURES = Path(__file__).parent / "fixtures" / "livetennis"
BASE_URL = "https://api.livetennisapi.com/api/public/v1"
NOW = datetime(2026, 9, 8, 10, 30, tzinfo=timezone.utc)


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def route_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/players"):
        return httpx.Response(200, json=load("players.json"))
    if path.endswith("/fixtures"):
        return httpx.Response(200, json=load("fixtures.json"))
    if path.endswith("/matches") and request.url.params.get("status") == "live":
        return httpx.Response(200, json=load("matches_live.json"))
    if path.endswith("/score"):
        return httpx.Response(200, json=load("score.json"))
    if "/matches/" in path:
        return httpx.Response(200, json=load("match_detail.json"))
    return httpx.Response(404, json={"error": "not_found"})


def build_provider(handler=route_handler):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(wrapped), base_url=BASE_URL, timeout=10.0
    )
    provider = LiveTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key="test-key",
        now=lambda: NOW,
    )
    return provider, seen, client


@pytest.fixture()
async def provider():
    built, seen, client = build_provider()
    try:
        yield built, seen
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_player_search_sends_api_key_and_query_and_maps_fields(provider) -> None:
    built, seen = provider

    players = await built.search_players("Sinner")

    assert seen[0].headers["X-API-Key"] == "test-key"
    assert seen[0].url.params["search"] == "Sinner"
    assert [player.name for player in players] == ["Jannik Sinner", "Casper Ruud"]
    assert players[0].id.startswith("ply_")
    assert players[0].country_code == "ita"
    assert players[0].ranking == 1
    assert players[1].country_code is None
    assert "101" not in players[0].id


@pytest.mark.asyncio
async def test_live_list_maps_vendor_payload_to_canonical(provider) -> None:
    built, seen = provider

    live = await built.get_live_matches()

    assert seen[0].url.path.endswith("/matches")
    assert seen[0].url.params["status"] == "live"
    assert len(live) == 1
    match = live[0]
    assert match.id.startswith("mat_")
    assert "21131" not in match.id
    assert match.status is MatchStatus.LIVE
    assert match.scheduled_at == datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc)
    assert match.round == "Semifinal"
    assert match.surface == "hard"
    assert match.indoor is True
    assert match.format == "BO3"
    assert match.tournament.name == "ATP Finals"
    assert match.tournament.tour == "atp"
    assert match.tournament.id.startswith("trn_")
    assert [player.name for player in match.players] == [
        "Jannik Sinner",
        "Carlos Alcaraz",
    ]

    state = match.live_state
    assert state is not None and state.score is not None
    assert state.score.sets_won == (1, 1)
    assert [(row.number, row.player1_games, row.player2_games) for row in state.score.sets] == [
        (1, 6, 4),
        (2, 4, 6),
        (3, 4, 5),
    ]
    assert state.score.points == ("30", "15")
    assert state.score.is_tiebreak is False
    assert state.server_player_id == match.players[0].id

    assert match.freshness.provider == "livetennis"
    assert match.freshness.observed_at == NOW
    assert match.freshness.source_updated_at == datetime(
        2026, 9, 8, 10, 0, tzinfo=timezone.utc
    )
    assert match.freshness.is_stale is False


@pytest.mark.asyncio
async def test_fixture_ids_share_match_namespace_and_keep_nulls(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    fixtures = await built.get_fixtures()

    assert len(fixtures) == 2
    fixture_ids = {match.id for match in fixtures}
    assert live[0].id in fixture_ids

    second = next(match for match in fixtures if match.id != live[0].id)
    assert second.scheduled_at is None
    assert second.round is None
    assert second.surface is None
    assert second.format is None
    assert second.status is MatchStatus.SCHEDULED
    assert second.players[1].id.startswith("ply_")
    assert second.players[1].name == "Winner of Q2"

    # Identity is stable across calls in the same process.
    fixtures_again = await built.get_fixtures()
    assert {match.id for match in fixtures_again} == fixture_ids
    assert [
        (match.players[0].id, match.players[1].id) for match in fixtures_again
    ] == [(match.players[0].id, match.players[1].id) for match in fixtures]


@pytest.mark.asyncio
async def test_get_match_detail_uses_external_id_and_maps_completed(provider) -> None:
    built, seen = provider

    live = await built.get_live_matches()
    detail = await built.get_match(live[0].id)

    detail_requests = [request for request in seen if request.url.path.endswith("/matches/21131")]
    assert len(detail_requests) == 1
    assert detail.id == live[0].id
    assert detail.status is MatchStatus.FINISHED
    assert detail.winner_player_id == detail.players[0].id


@pytest.mark.asyncio
async def test_get_score_maps_server_to_internal_id(provider) -> None:
    built, seen = provider

    live = await built.get_live_matches()
    state = await built.get_score(live[0].id)

    assert any(request.url.path.endswith("/matches/21131/score") for request in seen)
    assert state.score is not None
    assert [(row.player1_games, row.player2_games) for row in state.score.sets] == [
        (6, 4),
        (4, 6),
        (4, 5),
    ]
    assert state.server_player_id == live[0].players[0].id


@pytest.mark.asyncio
async def test_event_status_and_unknown_status_mapping() -> None:
    base_row = {
        "tournament": "ATP Finals",
        "tournament_id": "1217",
        "tour": "atp",
        "surface": None,
        "indoor": True,
        "format": None,
        "round": None,
        "status": "upcoming",
        "event_status": None,
        "scheduled_time": "2026-09-09T10:00:00Z",
        "players": {
            "p1": {"id": 201, "name": "Player One", "country": None, "ranking": None},
            "p2": {"id": 202, "name": "Player Two", "country": None, "ranking": None},
        },
        "score": None,
        "winner": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {**base_row, "id": 30001, "event_status": "Postponed"},
                    {**base_row, "id": 30002, "event_status": "Cancelled"},
                    {**base_row, "id": 30003, "status": "weird_future_status"},
                ],
                "meta": {},
            },
        )

    built, _, client = build_provider(handler)
    try:
        matches = await built.get_live_matches()
    finally:
        await client.aclose()

    assert [match.status for match in matches] == [
        MatchStatus.POSTPONED,
        MatchStatus.CANCELLED,
        MatchStatus.UNKNOWN,
    ]


@pytest.mark.asyncio
async def test_local_player_filter_uses_internal_ids(provider) -> None:
    built, _ = provider

    players = await built.search_players("Casper")
    ruud = next(player for player in players if player.name == "Casper Ruud")

    fixtures = await built.get_fixtures(player_id=ruud.id)
    assert len(fixtures) == 1
    assert any(player.id == ruud.id for player in fixtures[0].players)

    live = await built.get_live_matches(player_id=ruud.id)
    assert live == []


@pytest.mark.asyncio
async def test_unknown_internal_match_id_raises_not_found_without_network(provider) -> None:
    built, seen = provider

    with pytest.raises(AppError) as match_error:
        await built.get_match("mat_missing")
    assert match_error.value.code == "not_found"
    assert match_error.value.status_code == 404

    with pytest.raises(AppError) as score_error:
        await built.get_score("mat_missing")
    assert score_error.value.code == "not_found"

    assert seen == []


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


@pytest.mark.asyncio
async def test_vendor_fields_never_leak_into_canonical_models(provider) -> None:
    built, _ = provider

    live = await built.get_live_matches()
    fixtures = await built.get_fixtures()
    dumped = "".join(
        match.model_dump_json() for match in [*live, *fixtures]
    )

    for vendor_token in [
        "21131",
        "21140",
        "1217",
        "scheduled_time",
        "tournament_id",
        "event_status",
        "future_additive_field",
        '"p1"',
    ]:
        assert vendor_token not in dumped
