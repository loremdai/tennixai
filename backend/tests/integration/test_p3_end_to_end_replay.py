"""P3 dual-stream end-to-end replay integration (T70).

One deterministic fixture proves the whole chain against real PostgreSQL
and Redis: upcoming -> live -> finished sports state, both outcome books,
a provider correction, disconnect/reconcile with an explicit tracking gap,
BUY -> FILLED, HOLD -> SELL -> EXIT_MISSED, provider-final settlement and
the evaluation tracks. Two runs must produce identical digests, a restart
must recover cursors and demand from PostgreSQL alone, intents/fills must
never duplicate, and no provider identifier or secret may appear in any
public output. Requires compose PostgreSQL + Redis and
`uv run alembic upgrade head`.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from pathlib import Path

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import Settings
from app.decision.engine import DecisionEngine
from app.decision.policy import PolicyArtifact
from app.decision.worker import DecisionWorker, MarketRepositoryLinks, TrackingDemand
from app.markets.models import (
    MarketExecutionMetadata,
    MarketResolution,
    OutcomeBook,
    OutcomePayout,
    OrderBookState,
    ResolutionStatus,
)
from app.markets.publisher import MarketHotPublisher
from app.markets.replay import ReplayMarketFeed
from app.markets.worker import MarketWorker
from app.paper.service import PaperTradingService
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.prediction.models import (
    ModelAvailability,
    PredictionSnapshot,
    ProbabilityEstimate,
)
from app.providers.replay import ReplayTennisProvider
from app.realtime.p3_metrics import P3Metrics
from app.realtime.publisher import DecisionPublisher, PaperPublisher
from p3_fakes import make_market
from tests_support import FakeClock

pytestmark = pytest.mark.infrastructure

START = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "replay" / "p3_dual_stream.jsonl"
NO_ENTRY_FIXTURE = (
    Path(__file__).parent.parent
    / "fixtures"
    / "replay"
    / "p3_dual_stream_no_entry.jsonl"
)
POLICY_PATH = Path(__file__).parent.parent / "fixtures" / "decision" / "policy-v1.json"
TOKEN_A = "990007770001110002221"
TOKEN_B = "990007770001110002222"
DUAL_BOUNDS = [(0, 1200), (2600, 2600), (3000, 4200), (5200, 10**9)]
NO_ENTRY_BOUNDS = [(0, 50), (4500, 10**9)]
# Model view per market segment: entry window, disconnect hold, exit window,
# post-resolution. The stub predictor is a test double for the scoring stage;
# promotion evidence stays out of scope for the replay gate.
DUAL_PHASES = [0.72, 0.72, 0.30, None]


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


def load_dual(path: Path) -> tuple[list[dict], list[dict]]:
    sports: list[dict] = []
    market: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        (sports if record["stream"] == "sports" else market).append(record)
    return sports, market


def write_segments(
    market_records: list[dict], directory: Path, bounds: list[tuple[int, int]]
) -> list[Path]:
    """Split the market half into replay segments at the scripted breaks."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, (low, high) in enumerate(bounds):
        rows = [
            record for record in market_records if low <= record["t_offset_ms"] <= high
        ]
        path = directory / f"segment_{index}.jsonl"
        path.write_text(
            "\n".join(
                json.dumps(
                    {key: value for key, value in record.items() if key != "stream"},
                    separators=(",", ":"),
                )
                for record in rows
            )
            + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


async def _no_sleep(_seconds: float) -> None:
    return None


class StubPredictor:
    def __init__(self) -> None:
        self.prediction: PredictionSnapshot | None = None

    async def predict_snapshot(self, match_id: str, snapshot):
        if snapshot is None or self.prediction is None:
            return None
        return self.prediction


def prediction_for(match_id: str, player_a: str, player_b: str, prob: float):
    return PredictionSnapshot(
        match_id=match_id,
        outcomes=(
            ProbabilityEstimate(
                player_id=player_a,
                probability=prob,
                lower=round(prob - 0.05, 4),
                upper=round(prob + 0.05, 4),
            ),
            ProbabilityEstimate(
                player_id=player_b,
                probability=round(1 - prob, 4),
                lower=round(1 - prob - 0.05, 4),
                upper=round(1 - prob + 0.05, 4),
            ),
        ),
        availability=ModelAvailability.AVAILABLE,
        model_version="replay-m",
        calibration_version="replay-c",
        data_version="replay-d",
        input_state_version=1,
        as_of=START,
    )


def metadata_for(market_id: str) -> MarketExecutionMetadata:
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
        fetched_at=START,
    )


class HotBookSource:
    """Decision-side book source: the Redis hot book is the only market truth."""

    def __init__(self, publisher, metadata, ledger) -> None:
        self._publisher = publisher
        self._metadata = metadata
        self._ledger = ledger

    async def get_book(self, market_id: str):
        return await self._publisher.get_hot_book(market_id)

    async def get_metadata(self, market_id: str):
        return self._metadata

    async def get_rules_hash(self, market_id: str):
        return "rules_dual_v1"

    async def get_frozen_rules_hash(self, match_id: str):
        for intent in await self._ledger.load_all_intents():
            if intent.match_id == match_id:
                return intent.rules_hash
        return None


class SegmentRest:
    """Deterministic REST baseline for reconcile (network-free).

    The baseline mirrors the last known hot book so a reconnect reconcile
    confirms state instead of wiping it.
    """

    def __init__(self, player_a: str, player_b: str, now: datetime) -> None:
        self._player_a = player_a
        self._player_b = player_b
        self._now = now
        self.baseline: OrderBookState | None = None

    def _empty(self, market_id: str) -> OrderBookState:
        return OrderBookState(
            market_id=market_id,
            books=(
                OutcomeBook(outcome_player_id=self._player_a, bids=(), asks=()),
                OutcomeBook(outcome_player_id=self._player_b, bids=(), asks=()),
            ),
            sequence=0,
            book_hash=f"rest_dual_{market_id}",
            provider_timestamp=self._now,
            received_at=self._now,
        )

    async def get_order_book(self, market_id: str) -> OrderBookState:
        if self.baseline is not None:
            return self.baseline
        return self._empty(market_id)

    async def get_resolution(self, market_id: str) -> MarketResolution | None:
        return None


class Stack:
    """One full worker stack over real PostgreSQL + Redis."""

    def __init__(
        self,
        database: Database,
        redis_client,
        clock: FakeClock,
        market_id: str,
        player_a: str,
        player_b: str,
        first_segment: Path,
    ) -> None:
        self.clock = clock
        self.markets = MarketRepository(database)
        self.ledger = PaperLedgerRepository(database)
        self.market_publisher = MarketHotPublisher(redis_client, now_fn=clock.now)
        self.decision_publisher = DecisionPublisher(redis_client, now_fn=clock.now)
        self.paper_publisher = PaperPublisher(redis_client, now_fn=clock.now)
        self.predictor = StubPredictor()
        self.metadata = metadata_for(market_id)
        self.books = HotBookSource(self.market_publisher, self.metadata, self.ledger)
        self.rest = SegmentRest(player_a, player_b, clock.now())
        self.paper = PaperTradingService(
            ledger=self.ledger,
            clock=clock.now,
            publish=self.paper_publisher.publish_marker,
        )
        self.metrics = P3Metrics()
        self.market_worker = MarketWorker(
            feed=ReplayMarketFeed(
                first_segment, speed=10_000, now_fn=clock.now, sleep_fn=_no_sleep
            ),
            rest=self.rest,
            publisher=self.market_publisher,
            observations=self.markets,
            raw=self.markets,
            demand_source=self._demand,
            token_lookup=self._tokens,
            now=clock.now,
        )
        self.decision_worker = DecisionWorker(
            predictor=self.predictor,
            engine=DecisionEngine(
                policy=PolicyArtifact.load(POLICY_PATH), stake=Decimal("10")
            ),
            paper=self.paper,
            books=self.books,
            links=MarketRepositoryLinks(self.markets),
            observations=self.markets,
            positions=self.ledger,
            publisher=self.decision_publisher,
            metrics=self.metrics,
            clock=clock.now,
        )
        self.tracking = TrackingDemand(
            links=MarketRepositoryLinks(self.markets),
            match_info=None,
            ledger=self.ledger,
            now=clock.now,
            coverage_window=timedelta(minutes=240),
        )

    async def _demand(self) -> set[str]:
        return set((await MarketRepositoryLinks(self.markets).active_links()).values())

    async def _tokens(self, market_id: str) -> tuple[str, ...]:
        return (TOKEN_A, TOKEN_B)

    async def run_segment(self, path: Path) -> None:
        feed = ReplayMarketFeed(
            path, speed=10_000, now_fn=self.clock.now, sleep_fn=_no_sleep
        )
        await self.market_worker.run_replay_once(feed)

    async def hot_book(self, market_id: str) -> OrderBookState | None:
        return await self.market_publisher.get_hot_book(market_id)

    async def sync_book(self, market_id: str) -> OrderBookState | None:
        hot = await self.hot_book(market_id)
        if hot is not None:
            await self.decision_worker.handle_book(market_id, hot)
        return hot


async def digest_of(database: Database, match_id: str) -> str:
    async with database.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT observation_version, action, "
                    "is_stale, has_gap FROM decision_observations "
                    "WHERE match_id = :match_id ORDER BY observation_version"
                ),
                {"match_id": match_id},
            )
        ).all()
    observations = [tuple(row) for row in rows]
    ledger = PaperLedgerRepository(database)
    intents = await ledger.load_intents_for_match(match_id)
    position = await ledger.get_position(match_id)
    paper = [(intent.side.value, intent.status.value) for intent in intents]
    tracks = (
        [
            (track.track.value, track.exit_kind.value, str(track.net_pnl))
            for track in await ledger.load_track_results(position.id)
        ]
        if position is not None
        else []
    )
    settled = (position.status.value if position is not None else None, tracks)
    payload = json.dumps(
        {"observations": observations, "paper": paper, "settled": settled},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def run_scenario(
    *,
    tag: str,
    database: Database,
    redis_client,
    tmp_path: Path,
    fixture: Path = FIXTURE,
    restart_after_fill: bool = False,
) -> dict:
    sports_records, market_records = load_dual(fixture)
    bounds = DUAL_BOUNDS if fixture is FIXTURE else NO_ENTRY_BOUNDS
    phases = DUAL_PHASES if fixture is FIXTURE else [0.5, 0.5]
    segments = write_segments(market_records, tmp_path / tag, bounds)
    segment_starts: list[int] = []
    for low, _high in bounds:
        rows = [r for r in market_records if low <= r["t_offset_ms"] <= _high]
        segment_starts.append(rows[0]["t_offset_ms"] if rows else 10**9)
    clock = FakeClock(START)

    identity = PostgresIdentityRepository(database)
    provider = ReplayTennisProvider(
        tuple(
            {
                "at_ms": record["at_ms"],
                "match_id": record["match_id"],
                "kind": record["kind"],
                "payload": record["payload"],
            }
            for record in sports_records
        ),
        identities=identity,
        clock=clock,
        speed=10_000,
        identity_namespace=f"dual-{tag}",
    )
    stream = provider.stream_match(sports_records[0]["match_id"])

    markets = MarketRepository(database)

    first = await provider.to_candidate(await anext(stream))
    match_id = first.match.id
    player_a = first.match.players[0].id
    player_b = first.match.players[1].id
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_dual_{tag}",
        condition_id=f"0xdualcondition{tag}",
    )
    await markets.save_market(
        make_market(market_id, match_id=match_id, player_a=player_a, player_b=player_b)
    )
    await markets.link_match(
        market_id=market_id, match_id=match_id, evidence={"replay": tag}
    )

    stack = Stack(
        database, redis_client, clock, market_id, player_a, player_b, segments[0]
    )
    await stack.decision_worker.recover_cursors([match_id])

    paper_markers: list[str] = []
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"tnx:p3:paper:{match_id}")

    async def collect_markers() -> None:
        message = await pubsub.get_message(timeout=0.2)
        if message and message.get("type") == "message":
            paper_markers.append(str(message["data"]))

    def set_phase(index: int) -> None:
        prob = phases[index] if index < len(phases) else None
        stack.predictor.prediction = (
            None if prob is None else prediction_for(match_id, player_a, player_b, prob)
        )

    segment_index = 0
    entry_executed = False
    exit_executed = False
    restarted = False

    async def run_due_segment(index: int) -> None:
        nonlocal entry_executed, exit_executed
        if index == 1:
            # Reconnect reconcile must confirm, not wipe, the last book.
            stack.rest.baseline = await stack.hot_book(market_id)
        set_phase(index)
        await stack.run_segment(segments[index])
        await stack.sync_book(market_id)

    for record in sports_records[1:]:
        at_ms = record["at_ms"]
        while segment_index < len(segments) and segment_starts[segment_index] <= at_ms:
            await run_due_segment(segment_index)
            segment_index += 1

        if restart_after_fill and entry_executed and not restarted:
            restarted = True
            stack = Stack(
                database,
                redis_client,
                clock,
                market_id,
                player_a,
                player_b,
                segments[0],
            )
            await stack.decision_worker.recover_cursors([match_id])
            demanded = await stack.tracking.demanded_markets()
            assert market_id in demanded, (
                "restart must reload tracking demand from PostgreSQL alone"
            )
            position = await stack.ledger.get_position(match_id)
            assert position is not None and position.status.value == "open"

        envelope = await anext(stream)
        candidate = await provider.to_candidate(envelope)
        if envelope.kind == "disconnect":
            await stack.decision_worker.handle_sports(match_id, None)
        else:
            await stack.decision_worker.handle_sports(match_id, candidate)

        # The entry intent appears with the first post-book decision; execute
        # it once its sports delay is due against the verifiable hot book.
        if fixture is FIXTURE and not entry_executed:
            pending = [
                intent
                for intent in await stack.ledger.load_intents_for_match(match_id)
                if intent.status.value == "pending"
            ]
            if pending:
                clock.advance(2)
                await stack.paper.execute_due_intents(
                    book=await stack.hot_book(market_id),
                    metadata=stack.metadata,
                    market_id=market_id,
                )
                entry_executed = True

    while segment_index < len(segments):
        await run_due_segment(segment_index)
        segment_index += 1

    if fixture is FIXTURE:
        # Hot book lost with the disconnect: the exit intent can only be
        # recorded as an honest unverifiable NO_FILL (EXIT_MISSED).
        clock.advance(3)
        await stack.paper.execute_due_intents(
            book=None, metadata=stack.metadata, market_id=market_id
        )
        exit_executed = True

    resolution = MarketResolution(
        market_id=market_id,
        status=ResolutionStatus.FINAL,
        rules_version=1,
        payouts=(
            OutcomePayout(player_id=player_a, payout_per_share=Decimal("1")),
            OutcomePayout(player_id=player_b, payout_per_share=Decimal("0")),
        ),
        confirmed_at=clock.now(),
    )
    await stack.decision_worker.on_resolution(market_id, resolution)
    await stack.paper.settle_market(market_id, resolution)

    # Idempotence: re-running due-intent execution never duplicates fills.
    before = await stack.ledger.load_intents_for_match(match_id)
    clock.advance(5)
    await stack.paper.execute_due_intents(
        book=await stack.hot_book(market_id),
        metadata=stack.metadata,
        market_id=market_id,
    )
    after = await stack.ledger.load_intents_for_match(match_id)
    assert len(before) == len(after), "intent execution must stay idempotent"

    for _ in range(10):
        await collect_markers()
    await pubsub.unsubscribe(f"tnx:p3:paper:{match_id}")
    await pubsub.aclose()

    async with database.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT action FROM decision_observations "
                    "WHERE match_id = :match_id ORDER BY observation_version"
                ),
                {"match_id": match_id},
            )
        ).all()
    actions = [row[0] for row in rows]

    return {
        "match_id": match_id,
        "market_id": market_id,
        "actions": actions,
        "markers": paper_markers,
        "metrics": stack.metrics.export(),
        "digest": await digest_of(database, match_id),
        "stack": stack,
    }


async def test_dual_stream_replay_is_deterministic_end_to_end(
    database: Database, redis_client, tmp_path: Path
) -> None:
    digests = []
    for run in range(2):
        result = await run_scenario(
            tag=f"run{run}-{uuid4().hex[:8]}",
            database=database,
            redis_client=redis_client,
            tmp_path=tmp_path,
        )
        digests.append(result["digest"])
        if run == 0:
            stack = result["stack"]
            intents = await stack.ledger.load_intents_for_match(result["match_id"])
            sides = [intent.side.value for intent in intents]
            assert sides == ["entry", "exit"], f"one-shot lifecycle, got {sides}"
            fills = [intent for intent in intents if intent.status.value == "filled"]
            assert len(fills) == 1, "entry fills exactly once; exit stays NO_FILL"
            position = await stack.ledger.get_position(result["match_id"])
            assert position is not None
            assert position.status.value == "settled"
            tracks = await stack.ledger.load_track_results(position.id)
            ev_exit = [t for t in tracks if t.track.value == "ev_exit"]
            assert len(ev_exit) == 1, "all three evaluation tracks settle"
            assert len(tracks) == 3
            assert ev_exit[0].exit_kind.value == "exit_missed"
            assert "buy" in result["actions"] and "sell" in result["actions"]
            async with database.engine.connect() as connection:
                gap_rows = (
                    await connection.execute(
                        text(
                            "SELECT COUNT(*) FROM market_observations "
                            "WHERE market_id = :market_id AND kind = 'tracking_gap'"
                        ),
                        {"market_id": result["market_id"]},
                    )
                ).scalar()
                versions = (
                    (
                        await connection.execute(
                            text(
                                "SELECT observation_version FROM decision_observations "
                                "WHERE match_id = :match_id ORDER BY observation_version"
                            ),
                            {"match_id": result["match_id"]},
                        )
                    )
                    .scalars()
                    .all()
                )
            assert gap_rows >= 1, (
                "the market disconnect must surface as an explicit tracking gap"
            )
            assert list(versions) == list(range(1, len(versions) + 1)), (
                "decision versions stay contiguous and independent"
            )
            blob = json.dumps(
                {
                    "observations": result["actions"],
                    "metrics": result["metrics"],
                    "markers": result["markers"],
                }
            )
            for fragment in (
                TOKEN_A,
                TOKEN_B,
                "0xdualcondition",
                "dual-match",
                "dual-player",
                "TENNX_",
                "api_key",
            ):
                assert fragment not in blob
            assert stack.decision_worker.queue_overflow_total() == 0
    assert digests[0] == digests[1], "identical fixture runs must hash identically"


async def test_restart_recovers_cursors_and_demand_from_postgres(
    database: Database, redis_client, tmp_path: Path
) -> None:
    result = await run_scenario(
        tag=f"restart-{uuid4().hex[:8]}",
        database=database,
        redis_client=redis_client,
        tmp_path=tmp_path,
        restart_after_fill=True,
    )
    async with database.engine.connect() as connection:
        versions = (
            (
                await connection.execute(
                    text(
                        "SELECT observation_version FROM decision_observations "
                        "WHERE match_id = :match_id ORDER BY observation_version"
                    ),
                    {"match_id": result["match_id"]},
                )
            )
            .scalars()
            .all()
        )
    assert list(versions) == list(range(1, len(versions) + 1)), (
        "restart must resume the cursor without gaps or duplicates"
    )
    position = await result["stack"].ledger.get_position(result["match_id"])
    assert position is not None and position.status.value == "settled"


async def test_no_entry_fixture_settles_without_intents(
    database: Database, redis_client, tmp_path: Path
) -> None:
    result = await run_scenario(
        tag=f"noentry-{uuid4().hex[:8]}",
        database=database,
        redis_client=redis_client,
        tmp_path=tmp_path,
        fixture=NO_ENTRY_FIXTURE,
    )
    intents = await result["stack"].ledger.load_intents_for_match(result["match_id"])
    assert intents == [], "50-50 book with no edge must never create an intent"
    position = await result["stack"].ledger.get_position(result["match_id"])
    assert position is None
    assert result["actions"], "observations still record the honest NO BET/WAIT path"
    for action in result["actions"]:
        assert action not in ("buy", "sell")
