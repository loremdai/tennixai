"""P3 decision worker restart-recovery integration (T65).

After a restart the worker resumes decision version cursors from
PostgreSQL alone and tracking demand reloads unresolved positions and
active links without any viewer involvement. Requires compose PostgreSQL
+ `uv run alembic upgrade head`.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.config import Settings
from app.decision.engine import DecisionEngine
from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.decision.policy import PolicyArtifact
from app.decision.worker import DecisionWorker, MarketRepositoryLinks, TrackingDemand
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.realtime.p3_metrics import P3Metrics
from p3_fakes import make_entry_fill, make_intent, make_market, make_position
from tests_support import FakeClock

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent.parent / "fixtures" / "decision" / "policy-v1.json"


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


def observation(match_id: str, market_id: str, version: int) -> DecisionObservation:
    return DecisionObservation(
        match_id=match_id,
        market_id=market_id,
        action=DecisionAction.NO_BET,
        observation_version=version,
        reason_code="NO_NET_EDGE",
        model_version="m",
        calibration_version="c",
        policy_version="policy-v1",
        gates=(GateResult(gate="net_edge", passed=False, reason_code="NO_NET_EDGE"),),
        as_of=NOW,
    )


async def test_restart_resumes_decision_cursor_and_durable_demand(
    database: Database,
) -> None:
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    identity = PostgresIdentityRepository(database)

    match_id = await identity.get_or_create("match", "itest-t65", uuid4().hex[:10])
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{uuid4().hex[:8]}",
        condition_id=f"0x{uuid4().hex}",
    )
    await markets.save_market(make_market(market_id, match_id=match_id))
    await markets.link_match(
        market_id=market_id,
        match_id=match_id,
        evidence={"pair": ["ply_a", "ply_b"]},
    )
    for version in (1, 2, 3):
        await markets.save_decision_observation(
            observation(match_id, market_id, version)
        )
    intent = await ledger.create_intent(make_intent(match_id, market_id))
    await ledger.record_fill(
        make_entry_fill(intent.id), position=make_position(match_id, market_id)
    )

    # --- restart: fresh instances recover from PostgreSQL alone ---
    settings = Settings(_env_file=None)
    restarted_db = Database(settings.database_url)
    try:
        restarted_markets = MarketRepository(restarted_db)
        restarted_ledger = PaperLedgerRepository(restarted_db)

        demand = TrackingDemand(
            links=MarketRepositoryLinks(restarted_markets),
            match_info=None,  # positions alone must keep the market tracked
            ledger=restarted_ledger,
            now=lambda: NOW,
        )
        demanded = await demand.demanded_markets()
        assert market_id in demanded

        clock = FakeClock(NOW)
        log: list[str] = []

        class NullSink:
            def __init__(self) -> None:
                self.saved = []

            async def save_decision_observation(self, obs):
                self.saved.append(obs)

            async def latest_observation_version(self, match_id: str) -> int:
                latest = await restarted_markets.latest_decision_observation(match_id)
                return latest.observation_version if latest else 0

        class NullPublisher:
            async def publish_decision(self, obs):
                log.append("publish")

        class NullBooks:
            async def get_book(self, market_id):
                return None

            async def get_metadata(self, market_id):
                return None

            async def get_rules_hash(self, market_id):
                return "rules_v1"

            async def get_frozen_rules_hash(self, match_id):
                return None

        class NullPredictor:
            async def predict_snapshot(self, match_id, snapshot):
                return None

        class NullPositions:
            async def get_position(self, match_id):
                return await restarted_ledger.get_position(match_id)

        sink = NullSink()
        worker = DecisionWorker(
            predictor=NullPredictor(),
            engine=DecisionEngine(policy=PolicyArtifact.load(POLICY_PATH)),
            paper=ledger,
            books=NullBooks(),
            links=MarketRepositoryLinks(restarted_markets),
            observations=sink,
            positions=NullPositions(),
            publisher=NullPublisher(),
            metrics=P3Metrics(),
            clock=clock.now,
        )
        await worker.recover_cursors((match_id,))

        # The cursor resumes after the last durable version: a book update
        # with no prediction saves nothing, but the version counter is ready.
        assert worker.current_version(match_id) == 3
    finally:
        await restarted_db.dispose()
