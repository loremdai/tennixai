from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
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
from app.main import create_app
from app.providers.fake import FakeTennisProvider

UTC = timezone.utc
FIXED_NOW = "2026-09-08T10:00:00Z"


class StubProvider:
    def __init__(
        self,
        *,
        players: list[Player] | None = None,
        live: list[Match] | None = None,
        upcoming: list[Match] | None = None,
        matches: dict[str, Match] | None = None,
        list_error: AppError | None = None,
    ) -> None:
        self.players = players or []
        self.live = live or []
        self.upcoming = upcoming or []
        self.matches = matches or {}
        self.list_error = list_error

    async def search_players(self, query: str) -> list[Player]:
        normalized = query.strip().casefold()
        return [p for p in self.players if normalized in p.name.casefold()]

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        if self.list_error is not None:
            raise self.list_error
        return list(self.live)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        if self.list_error is not None:
            raise self.list_error
        return list(self.upcoming)

    async def get_match(self, match_id: str) -> Match:
        match = self.matches.get(match_id)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_score(self, match_id: str) -> LiveMatchState:
        match = await self.get_match(match_id)
        if match.live_state is None:
            raise AppError("not_found", "Score not available", 404)
        return match.live_state


async def stub_client(provider: StubProvider) -> AsyncClient:
    app = create_app(Settings(_env_file=None, fixed_now=FIXED_NOW), provider=provider)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_match_list_never_exposes_provider_ids(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "upcoming", "player": "Sinner"})
    body = response.json()

    assert response.status_code == 200
    assert body["data"][0]["id"].startswith("mat_")
    assert "external_id" not in response.text
    assert "fake-upcoming" not in response.text


@pytest.mark.asyncio
async def test_invalid_status_has_stable_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "finished"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_upcoming_list_carries_scheduled_match(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "upcoming"})
    body = response.json()

    assert response.status_code == 200
    assert len(body["data"]) == 1
    match = body["data"][0]
    assert match["status"] == "scheduled"
    assert match["scheduled_at"].startswith("2026-09-08T12:30:00")
    assert match["tournament"]["name"] == "ATP Finals"
    assert [player["name"] for player in match["players"]] == [
        "Jannik Sinner",
        "Carlos Alcaraz",
    ]
    assert match["freshness"]["provider"] == "fake"


@pytest.mark.asyncio
async def test_live_list_carries_score_and_server(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "live"})
    body = response.json()

    assert response.status_code == 200
    match = body["data"][0]
    assert match["status"] == "live"
    state = match["live_state"]
    assert state["score"]["sets_won"] == [1, 1]
    assert state["score"]["points"] == ["30", "15"]
    assert state["server_player_id"] == match["players"][0]["id"]


@pytest.mark.asyncio
async def test_player_search_returns_canonical_players(client: AsyncClient) -> None:
    response = await client.get("/api/v1/players/search", params={"q": "sinner"})
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["status"] == "resolved"
    assert body["data"]["player"]["name"] == "Jannik Sinner"
    assert body["data"]["player"]["id"].startswith("ply_")
    assert "fake-sinner" not in response.text


@pytest.mark.asyncio
async def test_player_search_requires_query(client: AsyncClient) -> None:
    response = await client.get("/api/v1/players/search", params={"q": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_request"
    assert "request_id" in body


@pytest.mark.asyncio
async def test_match_detail_round_trip(client: AsyncClient) -> None:
    listing = await client.get("/api/v1/matches", params={"status": "upcoming"})
    match_id = listing.json()["data"][0]["id"]

    response = await client.get(f"/api/v1/matches/{match_id}")
    body = response.json()

    assert response.status_code == 200
    assert body["data"]["match"]["id"] == match_id
    assert body["data"]["match"]["round"] == "Semifinal"
    assert body["data"]["match"]["surface"] == "hard"
    assert body["data"]["state_version"] >= 0
    assert body["data"]["as_of"]


@pytest.mark.asyncio
async def test_unknown_match_returns_typed_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches/mat_missing")
    body = response.json()

    assert response.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert response.headers["X-Request-ID"] == body["request_id"]


@pytest.mark.asyncio
async def test_ambiguous_player_returns_409_with_candidates() -> None:
    provider = StubProvider(
        players=[
            Player(id="ply_1", name="Jannik Sinner"),
            Player(id="ply_2", name="Sinner Jr."),
        ],
    )
    async with await stub_client(provider) as http_client:
        response = await http_client.get(
            "/api/v1/matches", params={"status": "live", "player": "Sinner"}
        )

    body = response.json()
    assert response.status_code == 409
    assert body["error"]["code"] == "ambiguous_player"
    assert body["error"]["details"]["candidates"] == [
        {"id": "ply_1", "name": "Jannik Sinner"},
        {"id": "ply_2", "name": "Sinner Jr."},
    ]


@pytest.mark.asyncio
async def test_provider_failure_maps_to_503_envelope() -> None:
    provider = StubProvider(list_error=AppError("provider_unavailable", "down", 503))
    async with await stub_client(provider) as http_client:
        response = await http_client.get("/api/v1/matches", params={"status": "live"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_quota_failure_maps_to_429_with_retry_after() -> None:
    provider = StubProvider(
        list_error=AppError(
            "rate_limited",
            "LiveTennisAPI quota exceeded",
            429,
            {"retry_after": "30"},
        )
    )
    async with await stub_client(provider) as http_client:
        response = await http_client.get("/api/v1/matches", params={"status": "live"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_request_id_is_generated_and_propagated(client: AsyncClient) -> None:
    generated = await client.get("/api/v1/health")
    assert generated.headers["X-Request-ID"].startswith("req_")

    echoed = await client.get("/api/v1/health", headers={"X-Request-ID": "req-abc"})
    assert echoed.headers["X-Request-ID"] == "req-abc"

    error = await client.get("/api/v1/matches/mat_missing", headers={"X-Request-ID": "req-err"})
    assert error.headers["X-Request-ID"] == "req-err"
    assert error.json()["request_id"] == "req-err"


@pytest.mark.asyncio
async def test_error_envelope_has_stable_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/matches", params={"status": "finished"})
    body = response.json()

    assert set(body.keys()) == {"error", "request_id"}
    assert set(body["error"].keys()) == {"code", "message", "details"}
    assert body["error"]["details"] == {}


@pytest.mark.asyncio
async def test_live_mode_requires_credentials() -> None:
    with pytest.raises(ValueError, match="TENNIX_LIVETENNIS_API_KEY"):
        Settings(_env_file=None, provider_mode="live")


@pytest.mark.asyncio
async def test_fixed_now_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        create_app(Settings(_env_file=None, fixed_now="2026-09-08T10:00:00"))


@pytest.mark.asyncio
async def test_explicit_fake_provider_injection() -> None:
    identities = MemoryIdentityRepository()
    provider = FakeTennisProvider(
        identities=identities,
        now=lambda: datetime(2026, 9, 8, 10, 0, tzinfo=UTC),
    )
    app = create_app(
        Settings(_env_file=None, fixed_now=FIXED_NOW),
        provider=provider,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        response = await http_client.get("/api/v1/matches", params={"status": "live"})

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
