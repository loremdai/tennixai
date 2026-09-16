"""P3 paper-mode assembly smoke against real PostgreSQL + Redis (T66).

Proves `create_app(p3_mode="paper")` mounts the whole P3 surface
(decision worker, tracking demand, paper service, query service, p3 redis)
and that the paper lifecycle publish wiring delivers `paper_delta` events
on the independent `tnx:p3:paper:{id}` channel — the string-marker
contract of PaperTradingService must never be routed to a publisher that
expects domain objects. Requires compose services.
"""

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app
from app.persistence.database import Database

pytestmark = pytest.mark.infrastructure


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.paper_positions')")
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL not reachable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def test_paper_mode_mounts_p3_surface_and_publishes_paper_deltas(
    database: Database,
) -> None:
    # Full P3 assembly requires the api_tennis provider mode (the only mode
    # that builds database + resolver together). The dummy key performs no
    # I/O at assembly time; lifespan (and thus the live worker) never runs.
    settings = Settings(
        _env_file=None,
        p3_mode="paper",
        provider_mode="api_tennis",
        api_tennis_api_key="dummy-assembly-key",
    )
    app = create_app(settings)
    try:
        assert app.state.decision_worker is not None
        assert app.state.p3_tracking_demand is not None
        assert app.state.p3_paper_service is not None
        assert app.state.p3_queries is not None
        assert app.state.p3_metrics is not None
        redis_client = app.state.p3_redis
        assert redis_client is not None

        # REST surface answers through the assembled query service.
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/paper/positions")
            assert response.status_code == 200
            assert "open" in response.json()
            response = await client.get("/api/v1/markets/opportunities")
            assert response.status_code == 200

        # The paper publish wiring carries string markers to the paper
        # namespace as paper_delta events (never to publish_decision).
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("tnx:p3:paper:mat_smoke")
        try:
            await asyncio.sleep(0.05)  # let the subscription register
            await app.state.p3_paper_service._publish("filled:mat_smoke")
            message = None
            for _ in range(100):
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.1
                )
                if message is not None:
                    break
            assert message is not None
            event = json.loads(message["data"])
            assert event["type"] == "paper_delta"
            assert event["state"] == "filled"
            assert event["id"] == "mat_smoke"
            hot = await redis_client.get("tnx:p3:paper:hot:mat_smoke")
            assert hot is not None
            assert json.loads(hot)["state"] == "filled"
            await redis_client.delete("tnx:p3:paper:hot:mat_smoke")
        finally:
            await pubsub.aclose()
    finally:
        if app.state.market_provider is not None:
            await app.state.market_provider.aclose()
        redis_client = getattr(app.state, "p3_redis", None)
        if redis_client is not None:
            await redis_client.aclose()
