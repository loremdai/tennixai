"""P3 market realtime recovery integration (T60).

Process restart must reload durable tracking demand from PostgreSQL alone,
REST-rebuild hot books and mark the offline interval as `tracking_gap`
without backfilling any signal, fill or observation from the gap.
Requires compose PostgreSQL + Redis and `uv run alembic upgrade head`.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
from sqlalchemy import func, select, text

from app.config import Settings
from app.markets.models import (
    BookLevel,
    Market,
    MarketOutcome,
    MarketStatus,
    OrderBookState,
    OutcomeBook,
)
from app.markets.publisher import MarketHotPublisher
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.models import MarketObservationRow
from app.persistence.paper_repositories import PaperLedgerRepository
from app.persistence.repositories import PostgresIdentityRepository
from p3_fakes import make_entry_fill, make_intent, make_position

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.market_observations')")
            )
            mapped = result.scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )
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
    try:
        client = aioredis.from_url(settings.redis_url)
        await client.ping()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Redis not reachable ({type(exc).__name__})")
    try:
        yield client
    finally:
        await client.aclose()


def rest_book(market_id: str) -> OrderBookState:
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_rec_a",
                bids=(BookLevel(price=Decimal("0.55"), size=Decimal("200")),),
                asks=(BookLevel(price=Decimal("0.57"), size=Decimal("150")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_rec_b",
                bids=(BookLevel(price=Decimal("0.43"), size=Decimal("180")),),
                asks=(BookLevel(price=Decimal("0.45"), size=Decimal("160")),),
            ),
        ),
        sequence=0,
        book_hash="rest_rebuild",
        provider_timestamp=NOW,
        received_at=NOW,
    )


async def load_tracking_demand(
    markets: MarketRepository, ledger: PaperLedgerRepository
) -> set[str]:
    """Durable P3 tracking demand: markets with an active exact link plus
    every market carrying an unsettled paper position."""
    demand: set[str] = set()
    for link in await markets.list_active_links():
        demand.add(link.market_id)
    for position in await ledger.load_unsettled_positions():
        demand.add(position.market_id)
    return demand


async def test_restart_reloads_demand_rebuilds_books_and_marks_gap(
    database: Database, redis_client
) -> None:
    settings = Settings(_env_file=None)
    markets = MarketRepository(database)
    ledger = PaperLedgerRepository(database)

    # --- durable state created "before the restart" ---
    identity = PostgresIdentityRepository(database)
    match_id = await identity.get_or_create("match", "itest-t60", uuid4().hex[:10])
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{uuid4().hex[:8]}",
        condition_id=f"0x{uuid4().hex}",
    )
    await markets.save_market(
        Market(
            id=market_id,
            question="Recovery moneyline",
            outcomes=(
                MarketOutcome(player_id="ply_rec_a", name="Recovery A"),
                MarketOutcome(player_id="ply_rec_b", name="Recovery B"),
            ),
            status=MarketStatus.OPEN,
            rules_version=1,
            match_id=match_id,
            provider="polymarket",
            observed_at=NOW,
        )
    )
    await markets.link_match(
        market_id=market_id,
        match_id=match_id,
        evidence={"pair": ["ply_rec_a", "ply_rec_b"]},
    )
    offline_started = NOW
    intent = await ledger.create_intent(make_intent(match_id, market_id))
    await ledger.record_fill(
        make_entry_fill(intent.id),
        position=make_position(match_id, market_id),
    )

    # --- "process 1" published a hot book, then Redis is lost ---
    publisher = MarketHotPublisher(redis_client, now_fn=lambda: NOW)
    await publisher.publish_book(market_id, rest_book(market_id))
    await redis_client.delete(publisher.hot_key(market_id))

    # --- restart: a brand new stack recovers from PostgreSQL alone ---
    restarted_db = Database(settings.database_url)
    restarted_redis = aioredis.from_url(settings.redis_url)
    try:
        restarted_markets = MarketRepository(restarted_db)
        restarted_ledger = PaperLedgerRepository(restarted_db)
        demand = await load_tracking_demand(restarted_markets, restarted_ledger)
        assert market_id in demand

        restarted_publisher = MarketHotPublisher(
            restarted_redis, now_fn=lambda: NOW + timedelta(minutes=5)
        )
        assert await restarted_publisher.get_hot_book(market_id) is None

        # REST rebuild for every demanded market, then record the offline
        # interval as an explicit tracking gap; nothing is backfilled.
        class FakeRest:
            def __init__(self) -> None:
                self.calls: list[str] = []

            async def get_order_book(self, requested: str) -> OrderBookState:
                self.calls.append(requested)
                return rest_book(requested)

        rest = FakeRest()
        for demanded in sorted(demand):
            state = await rest.get_order_book(demanded)
            await restarted_publisher.publish_book(demanded, state)
            await restarted_markets.record_tracking_gap(
                market_id=demanded,
                match_id=None,
                reason="process_restart",
                started_at=offline_started,
                ended_at=NOW + timedelta(minutes=5),
            )

        assert market_id in rest.calls
        recovered = await restarted_publisher.get_hot_book(market_id)
        assert recovered is not None
        assert recovered.book_hash == "rest_rebuild"

        async with restarted_db.session() as session:
            gap_count = await session.scalar(
                select(func.count())
                .select_from(MarketObservationRow)
                .where(
                    MarketObservationRow.market_id == market_id,
                    MarketObservationRow.kind == "tracking_gap",
                )
            )
            fabricated = await session.scalar(
                select(func.count())
                .select_from(MarketObservationRow)
                .where(
                    MarketObservationRow.market_id == market_id,
                    MarketObservationRow.kind.not_in(
                        ["tracking_gap", "book_change", "resolution_event"]
                    ),
                )
            )
        assert gap_count == 1
        assert fabricated == 0

        # The ledger still holds exactly one intent and one open position:
        # Redis/browser loss created and erased nothing.
        positions = await restarted_ledger.load_unsettled_positions()
        assert [position.match_id for position in positions].count(match_id) == 1
        pending = await restarted_ledger.load_pending_intents()
        assert intent.id not in {item.id for item in pending}
    finally:
        await restarted_db.dispose()
        await restarted_redis.aclose()
