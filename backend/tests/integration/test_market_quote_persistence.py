"""Latest-quote projection against real PostgreSQL (T85).

Proves idempotent upsert, source precedence, the reversible schema, raw
batch retention/purge and that the projection carries no provider identity.
Requires compose PostgreSQL + `uv run alembic upgrade head`.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.config import Settings
from app.markets.models import BookLevel
from app.markets.quote_snapshot import record_raw_batch
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
    build_quote_snapshot,
)
from app.persistence.database import Database
from app.persistence.market_repositories import (
    MarketQuoteSnapshotRepository,
    MarketRepository,
)
from app.persistence.repositories import RawProviderEventRepository
from p3_fakes import make_market

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = (
                await connection.execute(
                    text("SELECT to_regclass('public.market_quote_snapshots')")
                )
            ).scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL not reachable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("quote schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def _market(database: Database) -> str:
    markets = MarketRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev85_{uuid4().hex[:10]}",
        condition_id=f"cond85_{uuid4().hex}",
    )
    await markets.save_market(make_market(market_id, match_id=None))
    return market_id


def _record(
    market_id: str,
    *,
    as_of: datetime,
    digest: str,
    source: QuoteSource = QuoteSource.SNAPSHOT,
) -> QuoteSnapshotRecord:
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=source,
        state=QuoteState.SNAPSHOT,
        book_hash=digest,
        as_of=as_of,
        expires_at=as_of + timedelta(seconds=300),
        outcome_bids=("0.58", "0.40"),
        outcome_asks=("0.60", "0.42"),
        best_bid=("ply_a", "0.58"),
        best_ask=("ply_a", "0.60"),
        spread="0.0200",
        depth_usd="306.00",
    )


async def test_quote_upsert_is_idempotent_and_precedence_ordered(
    database: Database,
) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)

    assert await repo.upsert(_record(market_id, as_of=NOW, digest="h1")) is True
    # Identical rerun writes nothing.
    assert await repo.upsert(_record(market_id, as_of=NOW, digest="h1")) is False
    # An older quote never overwrites a newer one.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW - timedelta(seconds=5), digest="h0")
        )
        is False
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.book_hash == "h1"

    # The realtime lane may take over at the same instant.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW, digest="ws", source=QuoteSource.REALTIME)
        )
        is True
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.source is QuoteSource.REALTIME

    # A newer snapshot wins over an older realtime value.
    assert (
        await repo.upsert(
            _record(market_id, as_of=NOW + timedelta(seconds=1), digest="h2")
        )
        is True
    )
    stored = await repo.load(market_id)
    assert stored is not None and stored.book_hash == "h2"

    async with database.session() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM market_quote_snapshots WHERE market_id = :m"),
            {"m": market_id},
        )
    assert int(count) == 1


async def test_quote_projection_stores_no_provider_identity(database: Database) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)
    await repo.upsert(_record(market_id, as_of=NOW, digest="h1"))
    stored = await repo.load(market_id)
    assert stored is not None
    blob = stored.model_dump_json().lower()
    for fragment in ("token", "condition", "0x", "wallet", "private"):
        assert fragment not in blob


async def test_raw_batch_is_written_per_batch_and_purged_by_age(
    database: Database,
) -> None:
    raw = RawProviderEventRepository(database)
    marker = uuid4().hex[:10]

    def batch(tag: str) -> ClobBooksBatch:
        return ClobBooksBatch(
            books={
                "tok_a": TokenBook(
                    token_id="tok_a",
                    bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                    asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                    book_hash="ha",
                    provider_timestamp=NOW,
                )
            },
            missing_tokens=("tok_b",),
            malformed_tokens=(),
            raw=({"asset_id": "tok_a", "hash": "ha", "marker": f"{marker}-{tag}"},),
        )

    await record_raw_batch(raw, observed_at=NOW, batch=batch("fresh"), batch_index=0)
    # A leftover ancient batch proves the 14-day cleanup path.
    await record_raw_batch(
        raw, observed_at=NOW - timedelta(days=30), batch=batch("ancient"), batch_index=1
    )

    async def remaining() -> set[str]:
        async with database.session() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT payload->'books'->0->>'marker'"
                        " FROM raw_provider_events"
                        " WHERE kind = 'clob_books_batch'"
                        " AND payload->'books'->0->>'marker' LIKE :pattern"
                    ),
                    {"pattern": f"{marker}-%"},
                )
            ).scalars()
            return {value for value in rows if value}

    # One row per batch (never per token): both tagged rows landed.
    assert await remaining() == {f"{marker}-fresh", f"{marker}-ancient"}

    purged = await raw.purge_raw_events(NOW - timedelta(days=14))
    assert purged >= 1
    assert await remaining() == {f"{marker}-fresh"}  # only the fresh one survives


async def test_canonical_batch_projection_round_trips_through_postgres(
    database: Database,
) -> None:
    market_id = await _market(database)
    repo = MarketQuoteSnapshotRepository(database)
    batch = ClobBooksBatch(
        books={
            "tok_a": TokenBook(
                token_id="tok_a",
                bids=(BookLevel(price=Decimal("0.58"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash="ha",
                provider_timestamp=NOW,
            ),
            "tok_b": TokenBook(
                token_id="tok_b",
                bids=(BookLevel(price=Decimal("0.40"), size=Decimal("10")),),
                asks=(BookLevel(price=Decimal("0.42"), size=Decimal("10")),),
                book_hash="hb",
                provider_timestamp=NOW,
            ),
        },
        missing_tokens=(),
        malformed_tokens=(),
        raw=(),
    )
    record = build_quote_snapshot(
        market_id=market_id,
        token_ids=("tok_a", "tok_b"),
        player_ids=("ply_a", "ply_b"),
        batch=batch,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert await repo.upsert(record) is True
    stored = await repo.load(market_id)
    assert stored is not None
    assert stored.state is QuoteState.SNAPSHOT
    assert stored.outcome_asks == ("0.60", "0.42")
    assert stored.levels is not None and len(stored.levels) == 2
    assert stored.levels[0].outcome_player_id == "ply_a"

    # Bulk loading is one query and returns only the requested markets.
    many = await repo.load_many([market_id, "mkt_missing"])
    assert set(many) == {market_id}
    assert many[market_id].book_hash == stored.book_hash
