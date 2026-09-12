"""Canonical player ranking adapter contract tests (deterministic, MockTransport only)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.players.models import RankingMovement, Tour
from app.providers.api_tennis import ApiTennisProvider
from app.providers.fake import FakeTennisProvider

FIXTURES = Path(__file__).parent / "fixtures" / "api_tennis"
BASE_URL = "https://api.api-tennis.com/tennis/"
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
API_KEY = "test-key"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def route_handler(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    method = params.get("method")
    if method == "get_standings":
        event_type = params.get("event_type")
        rows = [
            row
            for row in load("standings.json")["result"]
            if row.get("league") == event_type
        ]
        return httpx.Response(200, json={"success": 1, "result": rows})
    return httpx.Response(200, json={"success": 1, "result": []})


def make_provider(seen: list[httpx.Request]) -> ApiTennisProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return route_handler(request)

    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return ApiTennisProvider(
        client=client,
        identities=MemoryIdentityRepository(),
        api_key=API_KEY,
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_get_rankings_maps_standings_to_internal_entries() -> None:
    seen: list[httpx.Request] = []
    provider = make_provider(seen)

    entries = await provider.get_rankings(Tour.ATP)

    assert seen[-1].url.params["method"] == "get_standings"
    assert seen[-1].url.params["event_type"] == "ATP"
    assert [entry.rank for entry in entries] == [1, 2, 3, 4, 200]
    first = entries[0]
    assert first.player.id.startswith("ply_")
    assert first.player.name == "Jannik Sinner"
    assert first.player.country_code == "ita"
    assert first.player.ranking == 1
    assert first.points == 11780
    assert first.tour is Tour.ATP
    assert first.ranking_date == NOW.date()
    assert first.fetched_at == NOW
    assert first.fetched_at.tzinfo is not None
    dumped = first.model_dump_json()
    assert "player_key" not in dumped
    assert API_KEY not in dumped
    assert entries[-1].player.country_code == "usa"


@pytest.mark.asyncio
async def test_get_rankings_maps_movement_and_falls_back_to_unknown() -> None:
    provider = make_provider([])

    entries = await provider.get_rankings(Tour.ATP)
    movements = {entry.rank: entry.movement for entry in entries}

    assert movements == {
        1: RankingMovement.SAME,
        2: RankingMovement.UP,
        3: RankingMovement.DOWN,
        4: RankingMovement.UNKNOWN,
        200: RankingMovement.DOWN,
    }


@pytest.mark.asyncio
async def test_get_rankings_skips_rows_without_usable_key_name_rank_or_points() -> None:
    provider = make_provider([])

    entries = await provider.get_rankings(Tour.ATP)

    # The fixture carries eight ATP rows; three are unusable.
    assert len(entries) == 5
    names = {entry.player.name for entry in entries}
    assert "Ghost Row" not in names
    assert "Bad Points" not in names


@pytest.mark.asyncio
async def test_get_rankings_reuses_internal_ids_across_calls() -> None:
    provider = make_provider([])

    first = await provider.get_rankings(Tour.ATP)
    second = await provider.get_rankings(Tour.ATP)

    assert [entry.player.id for entry in first] == [entry.player.id for entry in second]


@pytest.mark.asyncio
async def test_get_rankings_wta_parameter_and_china_mapping() -> None:
    seen: list[httpx.Request] = []
    provider = make_provider(seen)

    entries = await provider.get_rankings(Tour.WTA)

    assert seen[-1].url.params["event_type"] == "WTA"
    assert [entry.rank for entry in entries] == [1, 5]
    zheng = entries[1]
    assert zheng.player.name == "Qinwen Zheng"
    assert zheng.player.country_code == "chn"
    assert zheng.movement is RankingMovement.UP


@pytest.mark.asyncio
async def test_get_rankings_translates_vendor_failures() -> None:
    def unsuccessful(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": 0, "error": "boom"})

    provider = ApiTennisProvider(
        client=httpx.AsyncClient(
            base_url=BASE_URL, transport=httpx.MockTransport(unsuccessful)
        ),
        identities=MemoryIdentityRepository(),
        api_key=API_KEY,
        now=lambda: NOW,
    )
    with pytest.raises(AppError) as failure:
        await provider.get_rankings(Tour.ATP)
    assert failure.value.code == "provider_unavailable"

    def throttled(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"})

    provider = ApiTennisProvider(
        client=httpx.AsyncClient(
            base_url=BASE_URL, transport=httpx.MockTransport(throttled)
        ),
        identities=MemoryIdentityRepository(),
        api_key=API_KEY,
        now=lambda: NOW,
    )
    with pytest.raises(AppError) as failure:
        await provider.get_rankings(Tour.WTA)
    assert failure.value.code == "rate_limited"


@pytest.mark.asyncio
async def test_fake_provider_rankings_are_deterministic_and_span_required_cases() -> None:
    identities = MemoryIdentityRepository()
    fake = await FakeTennisProvider.create(identities, lambda: NOW)

    atp = await fake.get_rankings(Tour.ATP)
    wta = await fake.get_rankings(Tour.WTA)
    combined = atp + wta

    assert len(combined) >= 6
    assert {entry.tour for entry in combined} == {Tour.ATP, Tour.WTA}
    assert any(entry.player.country_code == "chn" for entry in combined)
    ranks = {entry.rank for entry in combined}
    assert 200 in ranks
    assert 201 in ranks
    assert {RankingMovement.UP, RankingMovement.DOWN, RankingMovement.SAME} <= {
        entry.movement for entry in combined
    }
    for entry in combined:
        assert entry.player.id.startswith("ply_")
        assert entry.fetched_at == NOW

    again = await fake.get_rankings(Tour.ATP)
    assert [entry.player.id for entry in again] == [entry.player.id for entry in atp]
    top = atp[0]
    assert top.player.name == "Jannik Sinner"
    assert "fake-" not in top.player.id
