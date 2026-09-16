"""P3 paper concurrency and restart-recovery integration (T64).

Two workers on the same BUY/SELL observation and a crash between commit and
publish must still leave exactly one intent, one fill, one position and one
settlement per match. Requires compose PostgreSQL + `uv run alembic upgrade
head`.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.config import Settings
from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.markets.models import (
    BookLevel,
    ExecutableQuote,
    MarketExecutionMetadata,
    MarketResolution,
    OrderBookState,
    OutcomeBook,
    OutcomePayout,
    QuoteSide,
    ResolutionStatus,
)
from app.paper.models import PositionStatus, TrackName
from app.paper.service import PaperTradingService
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.models import (
    PaperFillRow,
    PaperOrderIntentRow,
    PaperPositionRow,
    PaperTrackResultRow,
)
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from tests_support import FakeClock

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.paper_order_intents')")
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
async def identifiers(database: Database) -> tuple[str, str]:
    identity = PostgresIdentityRepository(database)
    match_id = await identity.get_or_create("match", "itest-t64", uuid4().hex[:10])
    markets = MarketRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{uuid4().hex[:8]}",
        condition_id=f"0x{uuid4().hex}",
    )
    from p3_fakes import make_market

    await markets.save_market(make_market(market_id, match_id=match_id))
    return match_id, market_id


def buy_observation(match_id: str, market_id: str) -> DecisionObservation:
    quote = ExecutableQuote(
        market_id=market_id,
        outcome_player_id="ply_a",
        side=QuoteSide.ENTRY,
        stake=Decimal("10.00"),
        shares=Decimal("19.230769"),
        average_price=Decimal("0.525"),
        fee=Decimal("0"),
        slippage=Decimal("0"),
        is_fillable=True,
        book_hash="book_signal",
        book_sequence=1,
        quoted_at=NOW,
    )
    return DecisionObservation(
        match_id=match_id,
        market_id=market_id,
        action=DecisionAction.BUY,
        observation_version=1,
        target_player_id="ply_a",
        model_version="m",
        calibration_version="c",
        policy_version="policy-v1",
        quote=quote,
        conservative_net_edge=Decimal("0.05"),
        gates=(GateResult(gate="liquidity", passed=True),),
        as_of=NOW,
    )


def executable_book(market_id: str) -> OrderBookState:
    def levels(raw):
        return tuple(BookLevel(price=Decimal(p), size=Decimal(s)) for p, s in raw)

    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=levels((("0.50", "200"),)),
                asks=levels((("0.52", "200"),)),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=levels((("0.47", "200"),)),
                asks=levels((("0.49", "200"),)),
            ),
        ),
        sequence=4,
        book_hash="book_exec",
        provider_timestamp=NOW,
        received_at=NOW,
    )


def metadata(market_id: str) -> MarketExecutionMetadata:
    return MarketExecutionMetadata(
        market_id=market_id,
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("5"),
        fee_rate=Decimal("0"),
        fee_exponent=Decimal("1"),
        taker_only=True,
        maker_base_fee=Decimal("0"),
        taker_base_fee=Decimal("0"),
        sports_delay_seconds=10,
        game_start_time=NOW,
        fetched_at=NOW,
    )


def final_resolution(market_id: str) -> MarketResolution:
    return MarketResolution(
        market_id=market_id,
        status=ResolutionStatus.FINAL,
        rules_version=1,
        payouts=(
            OutcomePayout(player_id="ply_a", payout_per_share=Decimal("1")),
            OutcomePayout(player_id="ply_b", payout_per_share=Decimal("0")),
        ),
        confirmed_at=NOW + timedelta(hours=2),
    )


def make_service(
    database: Database,
    clock: FakeClock,
    events: list[str],
    *,
    crash_on: str | None = None,
) -> PaperTradingService:
    ledger = PaperLedgerRepository(database)

    async def publish(event: str) -> None:
        if crash_on is not None and event.startswith(crash_on):
            raise RuntimeError("crash between commit and publish")
        events.append(event)

    return PaperTradingService(ledger=ledger, clock=clock.now, publish=publish)


async def _counts(database: Database, match_id: str) -> dict[str, int]:
    async with database.session() as session:
        intents = await session.scalar(
            select(func.count())
            .select_from(PaperOrderIntentRow)
            .where(PaperOrderIntentRow.match_id == match_id)
        )
        fills = await session.scalar(
            select(func.count())
            .select_from(PaperFillRow)
            .where(
                PaperFillRow.intent_id.in_(
                    select(PaperOrderIntentRow.id).where(
                        PaperOrderIntentRow.match_id == match_id
                    )
                )
            )
        )
        positions = await session.scalar(
            select(func.count())
            .select_from(PaperPositionRow)
            .where(PaperPositionRow.match_id == match_id)
        )
        tracks = await session.scalar(
            select(func.count())
            .select_from(PaperTrackResultRow)
            .where(PaperTrackResultRow.match_id == match_id)
        )
    return {
        "intents": int(intents or 0),
        "fills": int(fills or 0),
        "positions": int(positions or 0),
        "tracks": int(tracks or 0),
    }


async def test_two_workers_on_same_buy_produce_exactly_one_ledger(
    database: Database, identifiers
) -> None:
    match_id, market_id = identifiers
    clock = FakeClock(NOW)
    events: list[str] = []
    worker_a = make_service(database, clock, events)
    worker_b = make_service(database, clock, events)
    observation = buy_observation(match_id, market_id)
    book = executable_book(market_id)
    meta = metadata(market_id)

    await asyncio.gather(
        worker_a.on_decision(observation, book=book, metadata=meta, rules_hash="r1"),
        worker_b.on_decision(observation, book=book, metadata=meta, rules_hash="r1"),
    )
    clock.advance(11)
    await asyncio.gather(
        worker_a.execute_due_intents(book=book, metadata=meta, market_id=market_id),
        worker_b.execute_due_intents(book=book, metadata=meta, market_id=market_id),
    )

    counts = await _counts(database, match_id)
    assert counts == {"intents": 1, "fills": 1, "positions": 1, "tracks": 0}

    ledger = PaperLedgerRepository(database)
    position = await ledger.get_position(match_id)
    assert position is not None
    assert position.status is PositionStatus.OPEN


async def test_crash_between_commit_and_publish_recovers_exactly_once(
    database: Database, identifiers
) -> None:
    match_id, market_id = identifiers
    clock = FakeClock(NOW)
    events: list[str] = []
    crashing = make_service(database, clock, events, crash_on="filled")
    observation = buy_observation(match_id, market_id)
    book = executable_book(market_id)
    meta = metadata(market_id)

    await crashing.on_decision(observation, book=book, metadata=meta, rules_hash="r1")
    clock.advance(11)
    with pytest.raises(RuntimeError):
        await crashing.execute_due_intents(
            book=book, metadata=meta, market_id=market_id
        )

    # The fill committed before the crash; nothing may duplicate it.
    counts = await _counts(database, match_id)
    assert counts["intents"] == 1
    assert counts["fills"] == 1
    assert counts["positions"] == 1

    # Restart: a fresh service reloads durable state; pending intents are
    # empty (the intent is FILLED) and the open position is recoverable.
    restarted_events: list[str] = []
    restarted = make_service(database, clock, restarted_events)
    ledger = PaperLedgerRepository(database)
    pending = await ledger.load_pending_intents()
    assert match_id not in {intent.match_id for intent in pending}
    open_positions = await ledger.load_unsettled_positions()
    assert match_id in {position.match_id for position in open_positions}

    await restarted.execute_due_intents(book=book, metadata=meta, market_id=market_id)
    await restarted.settle_market(market_id, final_resolution(market_id))

    counts = await _counts(database, match_id)
    assert counts == {"intents": 1, "fills": 1, "positions": 1, "tracks": 3}
    position = await ledger.get_position(match_id)
    assert position is not None
    assert position.status is PositionStatus.SETTLED
    tracks = await ledger.load_track_results(position.id)
    assert {track.track for track in tracks} == {
        TrackName.EV_EXIT,
        TrackName.HODL_BASELINE,
        TrackName.CONVERGENCE_LOCK,
    }
