"""T76: the local `api` role serves canonical catalog reads and internal
runtime health without owning any upstream connection.

Deterministic only: no PostgreSQL, no Redis, no network, no external quota.
The API role must never construct a realtime worker, a live feed, or any
background discovery object — those belong to the `runtime` role (T77/T78).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Gender,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.main import create_app
from app.runtime.assembly import LocalRuntimeAssembly
from app.runtime.models import (
    LiveLocalConfigurationError,
    RuntimeHealth,
    RuntimeSourceHealth,
    RuntimeSourceStatus,
)

UTC = timezone.utc
FIXED_NOW = "2026-09-08T10:00:00Z"
NOW = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)


def local_api_settings(**overrides: Any) -> Settings:
    """Valid live-local settings for the `api` role with dummy credentials."""
    values: dict[str, Any] = {
        "fixed_now": FIXED_NOW,
        "provider_mode": "api_tennis",
        "api_tennis_api_key": "test-api-tennis-key",
        "llm_api_key": "test-llm-key",
        "llm_base_url": "https://llm.invalid/v1",
        "p3_mode": "paper",
        "local_runtime_role": "api",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# ---------------------------------------------------------------------------
# In-memory fakes: the focused role tests never touch real infrastructure.
# ---------------------------------------------------------------------------


class FakeDatabase:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeCatalog:
    """Stand-in for `MatchCatalogRepository.list_matches` (read side only)."""

    def __init__(self, matches: list[Match]) -> None:
        self.matches = matches
        self.calls: list[tuple[MatchStatus, str | None]] = []

    async def list_matches(
        self, status: MatchStatus, *, player_id: str | None = None
    ) -> list[Match]:
        self.calls.append((status, player_id))
        return [
            match
            for match in self.matches
            if match.status is status
            and (
                player_id is None
                or player_id in {player.id for player in match.players}
            )
        ]


class FakeState:
    def __init__(self, health: RuntimeHealth | None = None) -> None:
        self.health = health

    async def load_health(self) -> RuntimeHealth | None:
        return self.health


class RecordingProvider:
    """Any call proves a read leaked upstream; the API role must serve
    ordinary list reads from the canonical catalog only."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _record(self, name: str) -> None:
        self.calls.append(name)
        raise AssertionError(f"API role must not call provider.{name}")

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        self._record("get_live_matches")

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        self._record("get_fixtures")

    async def get_player(self, player_id: str) -> Player:
        self._record("get_player")

    async def get_match_snapshot(self, match_id: str) -> Any:
        self._record("get_match_snapshot")


def catalog_match(
    match_id: str = "mat_local_upcoming", status: MatchStatus = MatchStatus.SCHEDULED
) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=(
            Player(id="ply_a", name="Jannik Sinner", country_code="IT", ranking=1),
            Player(id="ply_b", name="Carlos Alcaraz", country_code="ES", ranking=2),
        ),
        tournament=Tournament(
            id="trn_finals",
            name="ATP Finals",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=datetime(2026, 9, 8, 12, 30, tzinfo=UTC),
        freshness=DataFreshness(provider="catalog", observed_at=NOW),
    )


def make_assembly(
    *, catalog: FakeCatalog, state: FakeState, provider: RecordingProvider
) -> LocalRuntimeAssembly:
    redis = FakeRedis()
    database = FakeDatabase()
    return LocalRuntimeAssembly(
        database=database,
        redis=redis,
        provider=provider,
        directory=None,
        resolver=None,
        catalog=catalog,
        state=state,
        realtime=SimpleNamespace(
            redis=redis, leases=None, publisher=None, store=None, worker=None
        ),
        p3_queries=None,
    )


@pytest.fixture()
async def env():
    provider = RecordingProvider()
    upcoming = catalog_match()
    live = catalog_match("mat_local_live", status=MatchStatus.LIVE)
    catalog = FakeCatalog([upcoming, live])
    state = FakeState(health=None)
    assembly = make_assembly(catalog=catalog, state=state, provider=provider)
    app = create_app(local_api_settings(), local_runtime=assembly)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield SimpleNamespace(
            app=app,
            client=client,
            provider=provider,
            catalog=catalog,
            state=state,
            assembly=assembly,
            upcoming=upcoming,
            live=live,
        )


# ---------------------------------------------------------------------------
# Ownership: the API role starts no worker and no upstream objects.
# ---------------------------------------------------------------------------


async def test_local_api_role_serves_catalog_without_starting_realtime_worker(env):
    async with env.app.router.lifespan_context(env.app):
        response = await env.client.get(
            "/api/v1/matches/catalog", params={"status": "upcoming"}
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["matches"][0]["id"] == env.upcoming.id
    assert env.app.state.realtime.worker is None
    # Canonical-first: the catalog answered, the provider was never touched.
    assert env.catalog.calls == [(MatchStatus.SCHEDULED, None)]
    assert env.provider.calls == []
    # Lifespan shutdown released the assembly-owned resources.
    assert env.assembly.database.disposed is True
    assert env.assembly.redis.closed is True


async def test_local_api_role_constructs_no_feed_or_background_objects(env):
    async with env.app.router.lifespan_context(env.app):
        pass

    assert env.app.state.realtime.worker is None
    assert env.app.state.market_feed is None
    assert env.app.state.decision_worker is None
    assert env.app.state.market_provider is None
    assert env.app.state.p3_tracking_demand is None


async def test_local_api_role_live_list_reads_canonical_status(env):
    response = await env.client.get("/api/v1/matches", params={"status": "live"})

    assert response.status_code == 200
    assert [match["id"] for match in response.json()["data"]] == [env.live.id]
    assert env.catalog.calls == [(MatchStatus.LIVE, None)]
    assert env.provider.calls == []


# ---------------------------------------------------------------------------
# Configuration gate: fail fast with stable typed codes, no secret echoes.
# ---------------------------------------------------------------------------


def test_local_api_role_rejects_invalid_configuration_before_any_client():
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        create_app(local_api_settings(provider_mode="fake"), local_runtime=None)
    assert excinfo.value.code == "LOCAL_PROVIDER_MODE_INVALID"

    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        create_app(local_api_settings(llm_api_key=None), local_runtime=None)
    assert excinfo.value.code == "LOCAL_CREDENTIALS_MISSING"
    # Stable reason code only: never the supplied URL, host or key material.
    assert "test-api-tennis-key" not in str(excinfo.value)
    assert "127.0.0.1" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Runtime health endpoint: internal aggregate only.
# ---------------------------------------------------------------------------


async def test_runtime_health_reports_typed_not_started(env):
    response = await env.client.get("/api/v1/runtime/health")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "runtime_not_started"
    assert body["data"] is None


async def test_runtime_health_serves_persisted_aggregate():
    health = RuntimeHealth(
        generated_at=NOW,
        sources={
            "catalog": RuntimeSourceHealth(
                status=RuntimeSourceStatus.OK,
                last_success_at=NOW,
                success_count=3,
                failure_count=0,
            ),
            "market_discovery": RuntimeSourceHealth(
                status=RuntimeSourceStatus.DEGRADED,
                reason_code="PROVIDER_TIMEOUT",
                success_count=1,
                failure_count=2,
            ),
        },
    )
    assembly = make_assembly(
        catalog=FakeCatalog([]),
        state=FakeState(health=health),
        provider=RecordingProvider(),
    )
    app = create_app(local_api_settings(), local_runtime=assembly)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/runtime/health")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ok"
    assert body["data"]["generated_at"].startswith("2026-09-08T10:00:00")
    sources = body["data"]["sources"]
    assert sources["catalog"]["status"] == "ok"
    assert sources["catalog"]["success_count"] == 3
    assert sources["market_discovery"]["reason_code"] == "PROVIDER_TIMEOUT"
    assert sources["market_discovery"]["failure_count"] == 2


async def test_runtime_health_dto_exposes_t78_aggregate_fields():
    health = RuntimeHealth(
        generated_at=NOW,
        sources={
            "polymarket": RuntimeSourceHealth(
                status=RuntimeSourceStatus.GAP,
                reason_code="CONNECTION_LOST",
                last_event_at=NOW,
                failure_count=1,
            ),
            "tennis_live": RuntimeSourceHealth(
                status=RuntimeSourceStatus.OK,
                last_success_at=NOW,
                last_tracked=3,
                success_count=5,
            ),
        },
        counters={"decision_suppressed": 2, "decision_queue_overflow": 0},
        paper_status="paper_only",
        model_status="not_promoted",
    )
    assembly = make_assembly(
        catalog=FakeCatalog([]),
        state=FakeState(health=health),
        provider=RecordingProvider(),
    )
    app = create_app(local_api_settings(), local_runtime=assembly)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/runtime/health")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sources"]["polymarket"]["status"] == "gap"
    assert data["sources"]["polymarket"]["last_event_at"] is not None
    assert data["sources"]["tennis_live"]["last_tracked"] == 3
    assert data["counters"] == {"decision_suppressed": 2, "decision_queue_overflow": 0}
    assert data["paper_status"] == "paper_only"
    assert data["model_status"] == "not_promoted"


async def test_runtime_health_response_contains_no_external_identifier_or_secret(
    env,
):
    body = (await env.client.get("/api/v1/runtime/health")).text

    for token in (
        "event_key",
        "conditionId",
        "APIkey",
        "test-api-tennis-key",
        "test-llm-key",
        "api-tennis.com",
        "wss://",
    ):
        assert token not in body


async def test_default_role_keeps_p1_health_contract_and_no_runtime_state(client):
    health = await client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "tennix-api"}

    runtime = await client.get("/api/v1/runtime/health")
    assert runtime.status_code == 200
    assert runtime.json()["state"] == "runtime_not_started"


async def test_build_local_runtime_assembly_constructs_offline_without_worker():
    """T76 review smoke: the real factory builds lazily (no I/O) and never
    constructs a realtime worker; every field is present and aclose works."""
    from app.runtime.assembly import build_local_runtime_assembly
    from app.runtime.config import require_live_local

    settings = local_api_settings()
    live = require_live_local(settings)
    assembly = build_local_runtime_assembly(settings, live, now=lambda: NOW)
    try:
        assert assembly.database is not None
        assert assembly.redis is not None
        assert assembly.provider is not None
        assert assembly.directory is not None
        assert assembly.resolver is not None
        assert assembly.catalog is not None
        assert assembly.state is not None
        assert assembly.p3_queries is not None
        # The API role never owns an upstream connection.
        assert assembly.realtime.worker is None
        assert assembly.realtime.leases is not None
        assert assembly.realtime.publisher is not None
        assert assembly.realtime.store is not None
    finally:
        await assembly.aclose()
