"""P3 latency gate with durable persistence (T70).

The deterministic in-memory gate lives in tests/test_p3_pipeline_metrics.py;
this integration variant pushes the same stage histograms through real
PostgreSQL observation writes and Redis hot-book publishes: book->decision
p95 must stay under 500ms and sports->decision p95 under 1s, queues must
not overflow, and two identical runs must hash identically. Requires
compose PostgreSQL + Redis and `uv run alembic upgrade head`.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import Settings
from app.decision.engine import DecisionEngine
from app.decision.policy import PolicyArtifact
from app.decision.worker import DecisionWorker, MarketRepositoryLinks
from app.markets.publisher import MarketHotPublisher
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.prediction.models import (
    ModelAvailability,
    PredictionSnapshot,
    ProbabilityEstimate,
)
from app.realtime.p3_metrics import P3Metrics
from app.realtime.publisher import DecisionPublisher
from p3_fakes import make_book, make_market
from tests_support import FakeClock

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent.parent / "fixtures" / "decision" / "policy-v1.json"
BOOK_CHANGES = 2_000
SPORTS_CHANGES = 500


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.decision_observations')")
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


@pytest.fixture()
async def redis_client():
    settings = Settings(_env_file=None)
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # pragma: no cover - environment dependent
        await client.aclose()
        pytest.skip(f"Redis not reachable ({type(exc).__name__})")
    try:
        yield client
    finally:
        await client.aclose()


class StubPredictor:
    def __init__(self, prediction) -> None:
        self._prediction = prediction

    async def predict_snapshot(self, match_id: str, snapshot):
        return self._prediction


class RedisBookSource:
    def __init__(self, publisher, metadata) -> None:
        self._publisher = publisher
        self._metadata = metadata

    async def get_book(self, market_id: str):
        return await self._publisher.get_hot_book(market_id)

    async def get_metadata(self, market_id: str):
        return self._metadata

    async def get_rules_hash(self, market_id: str):
        return "rules_latency_v1"

    async def get_frozen_rules_hash(self, match_id: str):
        return None


def prediction(match_id: str) -> PredictionSnapshot:
    return PredictionSnapshot(
        match_id=match_id,
        outcomes=(
            ProbabilityEstimate(
                player_id="ply_a", probability=0.62, lower=0.57, upper=0.67
            ),
            ProbabilityEstimate(
                player_id="ply_b", probability=0.38, lower=0.33, upper=0.43
            ),
        ),
        availability=ModelAvailability.AVAILABLE,
        model_version="lat-m",
        calibration_version="lat-c",
        data_version="lat-d",
        input_state_version=1,
        as_of=NOW,
    )


async def run_gate(database: Database, redis_client, tag: str) -> tuple[str, P3Metrics]:
    clock = FakeClock(NOW)
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    market_publisher = MarketHotPublisher(redis_client, now_fn=clock.now)
    decision_publisher = DecisionPublisher(redis_client, now_fn=clock.now)
    metrics = P3Metrics()

    match_id = f"mat_lat_{tag}"
    market_id = f"mkt_lat_{tag}"
    async with database.engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO matches (id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": match_id},
        )
    await markets.save_market(make_market(market_id, match_id=match_id))
    await markets.link_match(
        market_id=market_id, match_id=match_id, evidence={"latency": tag}
    )
    book = make_book(market_id)
    await market_publisher.publish_book(market_id, book)

    worker = DecisionWorker(
        predictor=StubPredictor(prediction(match_id)),
        engine=DecisionEngine(
            policy=PolicyArtifact.load(POLICY_PATH), stake=Decimal("10")
        ),
        paper=_NoopPaper(),
        books=RedisBookSource(
            market_publisher,
            metadata_for(market_id),
        ),
        links=MarketRepositoryLinks(markets),
        observations=markets,
        positions=ledger,
        publisher=decision_publisher,
        metrics=metrics,
        clock=clock.now,
    )

    started = time.perf_counter()
    for _ in range(SPORTS_CHANGES):
        await worker.handle_sports(match_id, snapshot=None)
    sports_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(BOOK_CHANGES):
        await worker.handle_book(market_id, book)
    book_elapsed = time.perf_counter() - started

    assert worker.queue_overflow_total() == 0
    assert book_elapsed < 60, f"book replay wall clock {book_elapsed:.1f}s"
    assert sports_elapsed < 60, f"sports replay wall clock {sports_elapsed:.1f}s"

    book_p95 = metrics.percentile("book_to_decision", 95)
    sports_p95 = metrics.percentile("sports_to_decision", 95)
    assert book_p95 < 500.0, f"book->decision p95 {book_p95:.1f}ms exceeds 500ms"
    assert sports_p95 < 1000.0, f"sports->decision p95 {sports_p95:.1f}ms exceeds 1s"

    async with database.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT observation_version, action FROM decision_observations "
                    "WHERE match_id = :match_id ORDER BY observation_version"
                ),
                {"match_id": match_id},
            )
        ).all()
    digest = hashlib.sha256(
        json.dumps([tuple(row) for row in rows], sort_keys=True, default=str).encode()
    ).hexdigest()
    return digest, metrics


def metadata_for(market_id: str):
    from app.markets.models import MarketExecutionMetadata

    return MarketExecutionMetadata(
        market_id=market_id,
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("5"),
        fee_rate=Decimal("0"),
        fee_exponent=Decimal("0"),
        taker_only=True,
        maker_base_fee=Decimal("0"),
        taker_base_fee=Decimal("0"),
        sports_delay_seconds=1,
        game_start_time=None,
        fetched_at=NOW,
    )


class _NoopPaper:
    """The latency gate measures the decision stage, not ledger commits."""

    async def on_decision(self, observation, **kwargs) -> None:
        return None

    async def settle_market(self, market_id, resolution, **kwargs) -> None:
        return None


async def test_latency_gate_holds_with_durable_persistence(
    database: Database, redis_client
) -> None:
    digests = []
    for run in range(2):
        digest, metrics = await run_gate(
            database, redis_client, f"{run}-{uuid4().hex[:6]}"
        )
        digests.append(digest)
        snapshot = json.loads(metrics.export())
        assert snapshot["counters"].get("queue_overflow", 0) == 0
    assert digests[0] == digests[1], "identical replay inputs must hash identically"
