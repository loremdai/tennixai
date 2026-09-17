"""Local runtime restart-recovery integration (T78).

A restarted daemon must rebuild subscriptions from durable demand, catalog
and ledger state in PostgreSQL alone (zero viewers), restore decision
cursors and the canonical hot book via REST, write an explicit gap BEFORE
recovery, execute a due paper intent exactly once against the restored hot
book, and create neither a duplicate intent nor a duplicate fill across
repeated ticks. Runs against a dedicated scratch database
(``tennix_runtime_recovery_test``) recreated and migrated per session, like
the T74 catalog integration; the legacy ``tennix`` database and the other
scratch databases are never touched. Requires compose PostgreSQL + Redis.
"""

import asyncio
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import asyncpg
import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_market_worker import (
    FakeMarketFeed,
    FakeObservationSink,
    FakeRaw,
    FakeRest,
)
from test_realtime_worker import candidate
from tests_support import FakeClock as DateTimeClock
from tests_support import build_service_inputs

from app.config import Settings
from app.decision.engine import DecisionEngine
from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.decision.policy import PolicyArtifact
from app.decision.worker import (
    DecisionWorker,
    MarketRepositoryLinks,
    TrackingDemand,
)
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
from app.markets.models import BookLevel, MarketExternalId, OrderBookState, OutcomeBook
from app.markets.publisher import MarketHotPublisher
from app.markets.worker import MarketWorker
from app.paper.service import PaperTradingService
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import (
    MatchCatalogRepository,
    PostgresIdentityRepository,
    RuntimeStateRepository,
)
from app.players.sync import DirectorySyncReport
from app.realtime.leases import ViewerLeaseStore
from app.realtime.p3_metrics import P3Metrics
from app.realtime.publisher import RealtimePublisher
from app.realtime.worker import RealtimeWorker
from app.runtime.daemon import (
    LocalRuntimeDaemon,
    MarketBridge,
    SportsBridge,
    TrackingDemandSource,
)
from app.runtime.demand import catalog_match_info
from app.runtime.health import MARKET_SOURCE, SPORTS_SOURCE, RuntimeHealthRegistry
from app.runtime.models import RuntimeSourceStatus
from p3_fakes import make_intent, make_market, make_rules
from realtime_fakes import (
    FakeClock as FloatClock,
    FakeLiveFeed,
    FakeRawRepository,
    FakeRestProvider,
    InMemoryRedis,
    InMemorySnapshotStore,
)

pytestmark = pytest.mark.infrastructure

SCRATCH_DATABASE_NAME = "tennix_runtime_recovery_test"
_PROTECTED_DATABASES = frozenset(
    {
        "postgres",
        "tennix",
        "tennix_live_local",
        "tennix_p3_shadow_preview",
        "tennix_runtime_test",
    }
)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent.parent / "fixtures" / "decision" / "policy-v1.json"
TOKEN_A = "990001112223334445551"
TOKEN_B = "990001112223334445552"
INPUTS = build_service_inputs()


def _base_url():
    return make_url(Settings(_env_file=None).database_url)


def _scratch_url() -> str:
    return (
        _base_url()
        .set(database=SCRATCH_DATABASE_NAME)
        .render_as_string(hide_password=False)
    )


def _admin_dsn(database: str) -> str:
    url = _base_url()
    return (
        f"postgresql://{url.username}:{quote_plus(url.password or '')}"
        f"@{url.host}:{url.port}/{database}"
    )


def _recreate_scratch_database() -> None:
    """Drop, recreate and migrate the scratch database (never a protected one)."""
    assert SCRATCH_DATABASE_NAME not in _PROTECTED_DATABASES
    assert _base_url().database != SCRATCH_DATABASE_NAME

    async def _recreate() -> None:
        connection = await asyncpg.connect(_admin_dsn("postgres"))
        try:
            await connection.execute(
                f"DROP DATABASE IF EXISTS {SCRATCH_DATABASE_NAME} WITH (FORCE)"
            )
            await connection.execute(f"CREATE DATABASE {SCRATCH_DATABASE_NAME}")
        finally:
            await connection.close()

    try:
        asyncio.run(_recreate())
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )
    env = {**os.environ, "TENNIX_DATABASE_URL": _scratch_url()}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def scratch_database_url() -> str:
    _recreate_scratch_database()
    return _scratch_url()


@pytest.fixture()
async def database(scratch_database_url: str):
    db = Database(scratch_database_url)
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


def fillable_book(market_id: str) -> OrderBookState:
    """REST baseline whose ply_a ask (0.51) sits inside the intent's price
    bound (0.525), so the due intent fills exactly once."""
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal("0.50"), size=Decimal("500")),),
                asks=(BookLevel(price=Decimal("0.51"), size=Decimal("500")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.47"), size=Decimal("500")),),
                asks=(BookLevel(price=Decimal("0.49"), size=Decimal("500")),),
            ),
        ),
        sequence=0,
        book_hash=f"rest_{market_id}",
        provider_timestamp=NOW,
        received_at=NOW,
    )


def catalog_match(match_id: str) -> Match:
    return Match(
        id=match_id,
        status=MatchStatus.LIVE,
        players=(
            Player(id="ply_a", name="Player One"),
            Player(id="ply_b", name="Player Two"),
        ),
        tournament=Tournament(
            id="trn_t78",
            name="Recovery Open",
            tour="atp",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=NOW,
        freshness=DataFreshness(provider="test", observed_at=NOW),
    )


class FlakyRealtime:
    """Proxy that fails the first reconcile to prove the explicit gap is
    persisted BEFORE recovery succeeds, then delegates to the real worker."""

    def __init__(self, worker: RealtimeWorker) -> None:
        self._worker = worker
        self.fail_next = True
        self.reconcile_calls = 0
        self.callback_failures = worker.callback_failures

    async def reconcile_demand_once(self) -> None:
        self.reconcile_calls += 1
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated_restart_failure")
        await self._worker.reconcile_demand_once()

    async def stop(self) -> None:
        await self._worker.stop()


class StubDiscoveryProvider:
    """No live markets during recovery; execution metadata is served for the
    single seeded market so the due intent can be verified."""

    def __init__(self, metadata) -> None:
        self._metadata = metadata
        self.metadata_calls: list[str] = []

    async def list_tennis_moneylines(self):
        return ()

    async def get_rules(self, market_id: str):
        raise AssertionError("no discovery rules expected")

    async def get_resolution(self, market_id: str):
        return None

    async def get_execution_metadata(self, market_id: str):
        self.metadata_calls.append(market_id)
        return self._metadata


class StubCatalogProvider:
    async def get_live_matches(self, *, player_id: str | None = None):
        return []

    async def get_fixtures(self, *, player_id: str | None = None):
        return []


class StubDirectory:
    async def sync_rankings(self) -> DirectorySyncReport:
        return DirectorySyncReport()

    async def sync_player_aliases(self, player_ids) -> DirectorySyncReport:
        return DirectorySyncReport()


class StubResolver:
    async def resolve(self, query: str, *, context_player_ids=(), limit: int = 5):
        raise AssertionError("no mapping expected during recovery")


async def paper_counts(db: Database, match_id: str) -> tuple[int, int, int]:
    async with db.engine.connect() as connection:
        intents = (
            await connection.execute(
                text("SELECT count(*) FROM paper_order_intents WHERE match_id = :m"),
                {"m": match_id},
            )
        ).scalar_one()
        fills = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM paper_fills f "
                    "JOIN paper_order_intents i ON f.intent_id = i.id "
                    "WHERE i.match_id = :m"
                ),
                {"m": match_id},
            )
        ).scalar_one()
        positions = (
            await connection.execute(
                text("SELECT count(*) FROM paper_positions WHERE match_id = :m"),
                {"m": match_id},
            )
        ).scalar_one()
    return int(intents), int(fills), int(positions)


async def test_restarted_daemon_recovers_from_durable_state_without_duplicates(
    database: Database, redis_client, scratch_database_url: str
) -> None:
    # --- seed durable pre-crash state (PostgreSQL is the only authority) ---
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)
    identity = PostgresIdentityRepository(database)
    catalog = MatchCatalogRepository(database)

    match_external = f"ext_{uuid4().hex[:10]}"
    match_id = await identity.get_or_create("match", "api_tennis", match_external)
    await catalog.upsert_matches([catalog_match(match_id)], observed_at=NOW)

    event_id = f"ev_{uuid4().hex[:8]}"
    condition_id = f"0x{uuid4().hex}"
    market_id = await markets.get_or_create_market_id(
        provider="polymarket", provider_event_id=event_id, condition_id=condition_id
    )
    await markets.save_market(make_market(market_id, match_id=match_id))
    await markets.save_rules(make_rules(market_id))
    await markets.save_external_id(
        MarketExternalId(
            market_id=market_id,
            provider="polymarket",
            provider_event_id=event_id,
            condition_id=condition_id,
            token_ids=(TOKEN_A, TOKEN_B),
        )
    )
    await markets.link_match(
        market_id=market_id,
        match_id=match_id,
        evidence={"pair": ["ply_a", "ply_b"]},
    )
    for version in (1, 2, 3):
        await markets.save_decision_observation(
            observation(match_id, market_id, version)
        )
    await ledger.create_intent(make_intent(match_id, market_id))
    assert await paper_counts(database, match_id) == (1, 0, 0)

    # --- restart: fresh instances rebuild from PostgreSQL/Redis alone ---
    restarted_db = Database(scratch_database_url)
    try:
        restarted_markets = MarketRepository(restarted_db)
        restarted_ledger = PaperLedgerRepository(restarted_db)
        restarted_identity = PostgresIdentityRepository(restarted_db)
        restarted_catalog = MatchCatalogRepository(restarted_db)
        state = RuntimeStateRepository(restarted_db)

        float_clock = FloatClock()
        dt_clock = DateTimeClock(NOW)

        def advance(seconds: float) -> None:
            float_clock.advance(seconds)
            dt_clock.advance(seconds=seconds)

        registry = RuntimeHealthRegistry(state=state, clock=dt_clock.now)
        metrics = P3Metrics()

        tracking = TrackingDemand(
            links=MarketRepositoryLinks(restarted_markets),
            match_info=catalog_match_info(restarted_catalog),
            ledger=restarted_ledger,
            now=dt_clock.now,
        )

        class NullDecisionSink:
            def __init__(self) -> None:
                self.saved: list[DecisionObservation] = []

            async def save_decision_observation(self, obs) -> None:
                self.saved.append(obs)

            async def latest_observation_version(self, match: str) -> int:
                latest = await restarted_markets.latest_decision_observation(match)
                return latest.observation_version if latest else 0

        class NullDecisionPublisher:
            async def publish_decision(self, obs) -> None:
                return None

        class NullBooks:
            async def get_book(self, market: str):
                return await market_publisher.get_hot_book(market)

            async def get_metadata(self, market: str):
                return INPUTS["metadata"].model_copy(update={"market_id": market})

            async def get_rules_hash(self, market: str):
                return "hash_v1"

            async def get_frozen_rules_hash(self, match: str):
                return None

        class NullPredictor:
            async def predict_snapshot(self, match: str, snapshot):
                return None

        class NullPositions:
            async def get_position(self, match: str):
                return await restarted_ledger.get_position(match)

        async def _publish(_message: str) -> None:
            return None

        paper = PaperTradingService(
            ledger=restarted_ledger,
            clock=dt_clock.now,
            publish=_publish,
        )

        decision_worker = DecisionWorker(
            predictor=NullPredictor(),
            engine=DecisionEngine(policy=PolicyArtifact.load(POLICY_PATH)),
            paper=paper,
            books=NullBooks(),
            links=MarketRepositoryLinks(restarted_markets),
            observations=NullDecisionSink(),
            positions=NullPositions(),
            publisher=NullDecisionPublisher(),
            metrics=metrics,
            clock=dt_clock.now,
            freshness_for=registry.freshness_for,
        )

        sports_bridge = SportsBridge(decision_worker=decision_worker, health=registry)
        market_bridge = MarketBridge(decision_worker=decision_worker, health=registry)

        # P2 side: zero viewers — demand must come from durable P3 tracking.
        viewer_redis = InMemoryRedis(float_clock)
        leases = ViewerLeaseStore(
            viewer_redis, lease_seconds=45, grace_seconds=60, now=float_clock.now
        )
        feed = FakeLiveFeed()
        realtime = RealtimeWorker(
            identity=restarted_identity,
            snapshots=InMemorySnapshotStore(),
            leases=leases,
            publisher=RealtimePublisher(viewer_redis, now=float_clock.utcnow),
            feed=feed,
            rest=FakeRestProvider([candidate(match_id, points=1)]),
            raw=FakeRawRepository(),
            now=float_clock.utcnow,
            max_live_subscriptions=8,
            demand_source=TrackingDemandSource(
                tracking=tracking,
                links=MarketRepositoryLinks(restarted_markets),
                health=registry,
            ),
            on_snapshot=sports_bridge.on_snapshot,
            on_connection=sports_bridge.on_connection,
        )

        # P3 market side: hot book is restored via REST into the real Redis
        # hot state, consumed by the daemon through MarketHotPublisher.
        market_publisher = MarketHotPublisher(redis_client, now_fn=dt_clock.now)
        market_rest = FakeRest()
        market_rest.books[market_id] = fillable_book(market_id)
        market_feed = FakeMarketFeed()

        async def tracked_token_lookup(market: str) -> tuple[str, str]:
            external = await restarted_markets.get_external_id(market)
            assert external is not None
            return external.token_ids

        market_worker = MarketWorker(
            feed=market_feed,
            rest=market_rest,
            publisher=market_publisher,
            observations=FakeObservationSink(),
            raw=FakeRaw(),
            demand_source=tracking.demanded_markets,
            token_lookup=tracked_token_lookup,
            now=dt_clock.now,
            on_state=market_bridge.on_state,
            on_connection=market_bridge.on_connection,
            metrics=metrics,
        )

        daemon = LocalRuntimeDaemon(
            realtime=FlakyRealtime(realtime),
            market_worker=market_worker,
            decision_worker=decision_worker,
            health=registry,
            clock=dt_clock.now,
            paper=paper,
            hot_books=market_publisher,
            market_provider=StubDiscoveryProvider(
                INPUTS["metadata"].model_copy(update={"market_id": market_id})
            ),
            markets=restarted_markets,
            ledger=restarted_ledger,
            catalog_provider=StubCatalogProvider(),
            catalog_store=restarted_catalog,
            directory=StubDirectory(),
            resolver=StubResolver(),
            metrics=metrics,
        )

        # 1) Recovery fails first: the explicit gap was persisted BEFORE any
        #    reconciliation succeeded, and new decisions stay revoked.
        await daemon.recover_once()
        gapped = await state.load_health()
        assert gapped is not None
        assert gapped.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.GAP
        assert gapped.sources[MARKET_SOURCE].status is RuntimeSourceStatus.GAP
        assert daemon.recovered is False
        overlay = await registry.freshness_for(match_id, market_id)
        assert overlay.has_gap is True

        # 2) Retry succeeds: subscriptions, cursors and the hot book are all
        #    rebuilt from durable state with zero viewers. The scratch
        #    database is recreated per session, so demand holds exactly the
        #    durable link this test seeded.
        await daemon.recover_once()
        assert daemon.recovered is True
        assert feed.opened_external_ids == [match_external]
        assert realtime.subscription_state(match_id) == "live"
        assert market_feed.subscribed[market_id] == (TOKEN_A, TOKEN_B)
        assert decision_worker.current_version(match_id) == 3
        restored_book = await market_publisher.get_hot_book(market_id)
        assert restored_book is not None
        assert restored_book.book_hash == f"rest_{market_id}"
        recovered = await state.load_health()
        assert recovered.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.OK
        assert recovered.sources[MARKET_SOURCE].status is RuntimeSourceStatus.OK
        assert (await registry.freshness_for(match_id, market_id)).has_gap is False

        # 3) The due intent executes exactly once against the restored hot
        #    book; a second tick never duplicates the intent or the fill.
        advance(20)
        await daemon.tick_once()
        first_counts = await paper_counts(restarted_db, match_id)
        assert first_counts == (1, 1, 1)

        await daemon.tick_once()
        assert await paper_counts(restarted_db, match_id) == first_counts

        # 4) Graceful shutdown closes both upstreams and persists final
        #    health; no data is deleted.
        await daemon.stop()
        assert match_external in feed.closed_external_ids
        assert market_id in market_feed.closed
        final = await state.load_health()
        assert final.generated_at == dt_clock.now()
        assert await paper_counts(restarted_db, match_id) == first_counts
    finally:
        await restarted_db.dispose()
