"""Player rankings/search/profile/results REST contract tests (fake mode)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app

FIXED_NOW = "2026-09-08T10:00:00Z"


@pytest.fixture()
async def client():
    app = create_app(Settings(_env_file=None, fixed_now=FIXED_NOW))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.mark.asyncio
async def test_rankings_default_page_is_atp_top200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/players/rankings")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["tour"] == "ATP"
    assert payload["page_size"] == 50
    ranks = [entry["rank"] for entry in payload["entries"]]
    assert ranks == sorted(ranks)
    assert payload["total"] == 5  # fake directory seeds five ATP entries


@pytest.mark.asyncio
async def test_rankings_rejects_bad_tour_page_and_page_size(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/players/rankings", params={"tour": "ITF"})).status_code == 422
    assert (await client.get("/api/v1/players/rankings", params={"page": 0})).status_code == 422
    assert (
        await client.get("/api/v1/players/rankings", params={"page_size": 25})
    ).status_code == 422


@pytest.mark.asyncio
async def test_rankings_wta_and_country_filter(client: AsyncClient) -> None:
    wta = await client.get("/api/v1/players/rankings", params={"tour": "WTA"})
    names = [entry["player"]["name"] for entry in wta.json()["data"]["entries"]]
    assert "Qinwen Zheng" in names

    china = await client.get(
        "/api/v1/players/rankings", params={"tour": "WTA", "country": "chn"}
    )
    entries = china.json()["data"]["entries"]
    assert entries and all(entry["player"]["country_code"] == "chn" for entry in entries)


@pytest.mark.asyncio
async def test_search_returns_resolution_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/players/search", params={"q": "Zheng"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "resolved"
    assert data["player"]["name"] == "Qinwen Zheng"

    missing = await client.get("/api/v1/players/search", params={"q": "zzz-nobody"})
    assert missing.status_code == 200
    assert missing.json()["data"]["status"] == "not_found"

    assert (await client.get("/api/v1/players/search")).status_code == 422


@pytest.mark.asyncio
async def test_profile_route_returns_view_and_404_for_unknown(
    client: AsyncClient,
) -> None:
    listing = await client.get("/api/v1/players/rankings", params={"tour": "WTA"})
    player_id = listing.json()["data"]["entries"][0]["player"]["id"]

    response = await client.get(f"/api/v1/players/{player_id}")
    assert response.status_code == 200
    view = response.json()["data"]
    assert view["selected_season"] == 2026
    assert view["profile"]["player"]["id"] == player_id

    missing = await client.get("/api/v1/players/ply_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_results_route_paginates_and_validates(client: AsyncClient) -> None:
    listing = await client.get("/api/v1/players/rankings", params={"tour": "WTA"})
    player_id = listing.json()["data"]["entries"][0]["player"]["id"]

    response = await client.get(
        f"/api/v1/players/{player_id}/results", params={"season": 2026}
    )
    assert response.status_code == 200
    page = response.json()["data"]
    assert page["page_size"] == 20
    assert page["total"] >= 20
    assert len(page["matches"]) == 20

    bad_season = await client.get(
        f"/api/v1/players/{player_id}/results", params={"season": 2019}
    )
    assert bad_season.status_code == 422
    bad_size = await client.get(
        f"/api/v1/players/{player_id}/results",
        params={"season": 2026, "page_size": 25},
    )
    assert bad_size.status_code == 422

    lost = await client.get(
        f"/api/v1/players/{player_id}/results",
        params={"season": 2026, "outcome": "lost"},
    )
    assert lost.status_code == 200
    matches = lost.json()["data"]["matches"]
    assert matches and all(match["winner_player_id"] != player_id for match in matches)


@pytest.mark.asyncio
async def test_static_routes_take_precedence_over_player_id(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/players/rankings")
    assert response.status_code == 200
    search = await client.get("/api/v1/players/search", params={"q": "Sinner"})
    assert search.status_code == 200
