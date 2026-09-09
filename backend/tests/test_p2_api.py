"""P2 REST APIs: match catalog endpoint, player results, and head-to-head."""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from p2_fakes import P2_NOW, CatalogFakeProvider

FIXED_NOW = "2026-09-09T12:00:00Z"


@pytest.fixture()
async def p2_env(catalog_provider: CatalogFakeProvider):
    catalog_provider.recent_results = [
        catalog_provider.finished_match("y", P2_NOW - timedelta(days=1)),
        catalog_provider.finished_match("older", P2_NOW - timedelta(days=4)),
    ]
    catalog_provider.h2h_meetings = [
        catalog_provider.finished_match("h0", P2_NOW - timedelta(days=2)),
        catalog_provider.finished_match("h1", P2_NOW - timedelta(days=20)),
        catalog_provider.finished_match("h2", P2_NOW - timedelta(days=40)),
    ]
    app = create_app(Settings(_env_file=None, fixed_now=FIXED_NOW), provider=catalog_provider)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client, catalog_provider


async def _player_id(http_client: AsyncClient, query: str) -> str:
    response = await http_client.get("/api/v1/players/search", params={"q": query})
    assert response.status_code == 200
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_catalog_endpoint_defaults_to_approved_facets(p2_env) -> None:
    http_client, provider = p2_env

    response = await http_client.get(
        "/api/v1/matches/catalog", params={"status": "upcoming"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["filters"] == {
        "circuits": ["atp", "wta"],
        "genders": [],
        "disciplines": ["singles"],
    }
    assert {match["id"] for match in data["matches"]} == {
        provider.sinner_alcaraz.id,
        provider.wta_upcoming.id,
    }
    assert data["featured_match_id"] == data["matches"][0]["id"]
    assert data["facet_counts"]["circuits"] == {
        "atp": 1,
        "wta": 1,
        "challenger": 1,
        "itf": 0,
        "other": 0,
    }
    assert data["facet_counts"]["genders"]["mixed"] == 0
    assert data["facet_counts"]["disciplines"]["singles"] == 2


@pytest.mark.asyncio
async def test_catalog_endpoint_stacks_facet_query_params(p2_env) -> None:
    http_client, provider = p2_env

    response = await http_client.get(
        "/api/v1/matches/catalog",
        params=[
            ("status", "upcoming"),
            ("circuit", "itf"),
            ("gender", "women"),
            ("discipline", "doubles"),
        ],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [match["id"] for match in data["matches"]] == [
        provider.itf_doubles_upcoming.id
    ]
    assert data["filters"]["circuits"] == ["itf"]
    assert data["filters"]["genders"] == ["women"]
    assert data["filters"]["disciplines"] == ["doubles"]


@pytest.mark.asyncio
async def test_catalog_endpoint_serves_live_status(p2_env) -> None:
    http_client, provider = p2_env

    response = await http_client.get(
        "/api/v1/matches/catalog", params={"status": "live"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert {match["id"] for match in data["matches"]} == {
        provider.live_match.id,
        provider.wta_live.id,
    }
    assert all(match["status"] == "live" for match in data["matches"])


@pytest.mark.asyncio
async def test_catalog_endpoint_rejects_invalid_inputs(p2_env) -> None:
    http_client, _ = p2_env

    response = await http_client.get(
        "/api/v1/matches/catalog", params={"status": "finished"}
    )
    assert response.status_code == 422

    response = await http_client.get(
        "/api/v1/matches/catalog",
        params={"status": "upcoming", "circuit": "grand_slam"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_player_results_endpoint_yesterday_scope(p2_env) -> None:
    http_client, provider = p2_env
    sinner = await _player_id(http_client, "sinner")

    response = await http_client.get(
        f"/api/v1/players/{sinner}/results",
        params={"scope": "yesterday", "limit": 5},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["player_id"] == sinner
    assert data["scope"] == "yesterday"
    assert data["availability"] == "available"
    # 2026-09-08T12:00Z is yesterday in Asia/Macau; -4d is not.
    assert [match["id"] for match in data["matches"]] == ["mat_hist_y"]
    assert all(match["status"] == "finished" for match in data["matches"])


@pytest.mark.asyncio
async def test_player_results_endpoint_validation(p2_env) -> None:
    http_client, _ = p2_env
    sinner = await _player_id(http_client, "sinner")

    response = await http_client.get(
        f"/api/v1/players/{sinner}/results", params={"scope": "lastyear"}
    )
    assert response.status_code == 422

    response = await http_client.get(
        f"/api/v1/players/{sinner}/results", params={"scope": "recent", "limit": 0}
    )
    assert response.status_code == 422

    response = await http_client.get(
        f"/api/v1/players/{sinner}/results", params={"scope": "recent", "limit": 11}
    )
    assert response.status_code == 422

    response = await http_client.get(
        "/api/v1/players/ply_missing/results", params={"scope": "recent"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_head_to_head_endpoint_maps_and_bounds(p2_env) -> None:
    http_client, _ = p2_env
    sinner = await _player_id(http_client, "sinner")
    ruud = await _player_id(http_client, "ruud")

    response = await http_client.get(
        "/api/v1/head-to-head",
        params={"first_player_id": sinner, "second_player_id": ruud, "limit": 2},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["availability"] == "available"
    assert data["head_to_head"]["first_player_id"] == sinner
    assert data["head_to_head"]["second_player_id"] == ruud
    assert len(data["head_to_head"]["meetings"]) == 2

    response = await http_client.get(
        "/api/v1/head-to-head", params={"first_player_id": sinner}
    )
    assert response.status_code == 422

    response = await http_client.get(
        "/api/v1/head-to-head",
        params={"first_player_id": sinner, "second_player_id": ruud, "limit": 42},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_p2_responses_leak_no_vendor_or_fake_ids(p2_env) -> None:
    http_client, _ = p2_env

    catalog = await http_client.get(
        "/api/v1/matches/catalog", params={"status": "upcoming"}
    )
    sinner = await _player_id(http_client, "sinner")
    results = await http_client.get(
        f"/api/v1/players/{sinner}/results", params={"scope": "recent"}
    )

    for body in (catalog.text, results.text):
        for token in ("event_key", "event_first_player", "first_player_key", "fake-"):
            assert token not in body


@pytest.mark.asyncio
async def test_p1_matches_endpoint_shape_is_unchanged(p2_env) -> None:
    http_client, provider = p2_env

    response = await http_client.get("/api/v1/matches", params={"status": "live"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"data"}
    assert {match["id"] for match in payload["data"]} == {
        provider.live_match.id,
        provider.wta_live.id,
    }


@pytest.mark.asyncio
async def test_catalog_literal_route_takes_precedence_over_match_id(p2_env) -> None:
    http_client, provider = p2_env

    response = await http_client.get(f"/api/v1/matches/{provider.live_match.id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == provider.live_match.id

    response = await http_client.get("/api/v1/matches/catalog")
    assert response.status_code == 422  # missing status param, not swallowed by /{match_id}
