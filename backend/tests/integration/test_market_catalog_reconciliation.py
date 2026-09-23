"""Full-catalog listing upsert and failure-safe retirement (T91)."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from app.markets.models import (
    MarketListing,
    MarketListingScan,
    MarketStatus,
)
from app.markets.quotes import QuoteSnapshotRecord
from app.markets.quotes import QuoteSource, QuoteState
from app.markets.quotes import realtime_listing_quote_record
from app.persistence.market_repositories import (
    MarketQuoteSnapshotRepository,
    MarketRepository,
)
from app.persistence.database import Database
from p3_fakes import NOW, make_market, make_rules


pytestmark = pytest.mark.infrastructure


def _condition() -> str:
    return f"0x{uuid4().hex}"


def _listing(
    market_id: str,
    *,
    names=("Player One", "Player Two"),
    player_ids=(None, None),
    status=MarketStatus.OPEN,
):
    return MarketListing(
        id=market_id,
        question=f"{names[0]} vs. {names[1]}: Match Winner",
        outcome_names=names,
        outcome_player_ids=player_ids,
        status=status,
        event_start=NOW,
        event_end=NOW + timedelta(hours=3),
        provider="polymarket",
        observed_at=NOW,
    )


@pytest.fixture()
async def database():
    from app.config import Settings
    from sqlalchemy import text

    db = Database(Settings(_env_file=None).database_url)
    try:
        async with db.engine.connect() as connection:
            mapped = await connection.scalar(
                text("SELECT to_regclass('public.markets')")
            )
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(f"PostgreSQL unavailable ({type(exc).__name__})")
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


async def test_complete_scan_closes_only_unseen_active_and_preserves_history(
    database: Database,
):
    markets = MarketRepository(database)
    quotes = MarketQuoteSnapshotRepository(database)
    active_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
        token_ids=("token-a", "token-b"),
    )
    retired_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
        token_ids=("token-c", "token-d"),
    )
    resolved_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
    )
    await markets.save_market(make_market(active_id))
    await markets.save_market(make_market(retired_id, status=MarketStatus.SCHEDULED))
    await markets.save_market(make_market(resolved_id, status=MarketStatus.RESOLVED))
    await markets.save_rules(make_rules(retired_id))
    await markets.link_match(
        market_id=retired_id,
        match_id=f"match_{uuid4().hex}",
        evidence={"method": "test"},
    )
    await quotes.upsert(
        QuoteSnapshotRecord(
            market_id=retired_id,
            source=QuoteSource.SNAPSHOT,
            state=QuoteState.SNAPSHOT,
            as_of=NOW,
            expires_at=NOW + timedelta(minutes=5),
            outcome_bids=("0.51", "0.47"),
            outcome_asks=("0.53", "0.49"),
        )
    )

    listing = _listing(active_id)
    new_strict = _listing(
        f"mkt_strict_{uuid4().hex[:8]}",
        names=("Resolved A", "Resolved B"),
        player_ids=("ply_a", "ply_b"),
    )
    new_unknown = _listing(
        "mkt_display_only", names=("Team A / Team B", "Team C / Team D")
    )
    retired_count = await markets.reconcile_market_listings(
        MarketListingScan(listings=(listing, new_strict, new_unknown), complete=True),
        observed_at=NOW + timedelta(minutes=1),
    )

    assert retired_count >= 1
    assert (await markets.get_market(active_id)).outcomes[0].player_id == "ply_a"
    strict_market = await markets.get_market(new_strict.id)
    assert strict_market is not None
    assert [outcome.player_id for outcome in strict_market.outcomes] == [
        "ply_a",
        "ply_b",
    ]
    assert await markets.get_market("mkt_display_only") is None
    rows = {row.market_id: row for row in await markets.list_market_overviews()}
    assert rows["mkt_display_only"].outcome_a_name == "Team A / Team B"
    assert rows["mkt_display_only"].outcome_a_player_id is None
    assert rows[retired_id].status == MarketStatus.CLOSED.value
    assert rows[resolved_id].status == MarketStatus.RESOLVED.value
    assert await markets.get_external_id(retired_id) is not None
    assert await markets.get_current_rules(retired_id) is not None
    assert await quotes.load(retired_id) is not None
    assert any(row.market_id == retired_id for row in await markets.list_active_links())


async def test_incomplete_scan_upserts_seen_rows_but_never_retires_old_rows(
    database: Database,
):
    markets = MarketRepository(database)
    old_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
    )
    await markets.save_market(make_market(old_id))
    new_listing = _listing(
        f"mkt_partial_{uuid4().hex[:8]}", names=("Unknown A", "Unknown B")
    )

    changed_count = await markets.reconcile_market_listings(
        MarketListingScan(listings=(new_listing,), complete=False),
        observed_at=NOW + timedelta(minutes=1),
    )

    rows = {row.market_id: row for row in await markets.list_market_overviews()}
    assert changed_count == 1
    assert rows[old_id].status == MarketStatus.OPEN.value
    assert rows[new_listing.id].outcome_b_name == "Unknown B"


async def test_unchanged_listing_scan_reports_no_display_changes(database: Database):
    markets = MarketRepository(database)
    listing = _listing(f"mkt_stable_{uuid4().hex[:8]}")
    first = await markets.reconcile_market_listings(
        MarketListingScan(listings=(listing,), complete=False), observed_at=NOW
    )

    # Provider timestamps advance on every scan; unchanged visible data must
    # not generate a catalog/SSE invalidation.
    rescanned = listing.model_copy(update={"observed_at": NOW + timedelta(minutes=2)})
    second = await markets.reconcile_market_listings(
        MarketListingScan(listings=(rescanned,), complete=False),
        observed_at=NOW + timedelta(minutes=2),
    )
    stored = {row.market_id: row for row in await markets.list_market_overviews()}[
        listing.id
    ]

    assert first == 1
    assert second == 0
    assert stored.observed_at == NOW + timedelta(minutes=2)
    assert stored.updated_at == NOW


async def test_market_catalog_order_is_stable_when_update_times_tie(database: Database):
    markets = MarketRepository(database)
    suffix = uuid4().hex[:8]
    ids = [f"mkt_order_{suffix}_{letter}" for letter in "cba"]
    await markets.reconcile_market_listings(
        MarketListingScan(
            listings=tuple(_listing(market_id) for market_id in ids), complete=False
        ),
        observed_at=NOW + timedelta(days=30),
    )

    rows = await markets.list_market_overviews()
    actual = [row.market_id for row in rows if row.market_id in set(ids)]

    assert actual == sorted(ids)


async def test_catalog_upsert_failure_rolls_back_updates_and_retirement(
    database: Database,
):
    markets = MarketRepository(database)
    old_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
    )
    await markets.save_market(make_market(old_id))
    first = _listing(f"mkt_good_{uuid4().hex[:8]}", names=("Known A", "Known B"))
    invalid = _listing("mkt_" + "x" * 70)

    with pytest.raises(DBAPIError):
        await markets.reconcile_market_listings(
            MarketListingScan(listings=(first, invalid), complete=True),
            observed_at=NOW + timedelta(minutes=1),
        )

    rows = {row.market_id: row for row in await markets.list_market_overviews()}
    assert old_id in rows and rows[old_id].status == MarketStatus.OPEN.value
    assert first.id not in rows


async def test_idless_snapshot_quote_roundtrips_without_outcome_books(
    database: Database,
):
    markets = MarketRepository(database)
    quotes = MarketQuoteSnapshotRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
        token_ids=("token-a", "token-b"),
    )
    listing = _listing(
        market_id,
        names=("Unresolved A", "Unresolved B"),
        player_ids=(None, None),
    )
    await markets.reconcile_market_listings(
        MarketListingScan(listings=(listing,), complete=False), observed_at=NOW
    )
    record = QuoteSnapshotRecord(
        market_id=market_id,
        source=QuoteSource.SNAPSHOT,
        state=QuoteState.SNAPSHOT,
        as_of=NOW,
        expires_at=NOW + timedelta(minutes=5),
        outcome_bids=("0.58", "0.40"),
        outcome_asks=("0.60", "0.42"),
        spread="0.0200",
        depth_usd="46.60",
    )

    assert await quotes.upsert(record) is True
    stored = await quotes.load(market_id)

    assert stored is not None
    assert stored.outcome_bids == ("0.58", "0.40")
    assert stored.outcome_asks == ("0.60", "0.42")
    assert stored.spread == "0.0200"
    assert stored.depth_usd == "46.60"
    assert stored.levels is None


async def test_idless_realtime_quote_roundtrips_without_outcome_books(
    database: Database,
):
    markets = MarketRepository(database)
    quotes = MarketQuoteSnapshotRepository(database)
    market_id = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"event_{uuid4().hex}",
        condition_id=_condition(),
        token_ids=("token-a", "token-b"),
    )
    listing = _listing(
        market_id,
        names=("Doubles Team A", "Doubles Team B"),
        player_ids=(None, None),
    )
    await markets.reconcile_market_listings(
        MarketListingScan(listings=(listing,), complete=False), observed_at=NOW
    )
    record = realtime_listing_quote_record(
        market_id=market_id,
        outcome_bids=("0.57", "0.39"),
        outcome_asks=("0.59", "0.41"),
        as_of=NOW,
        fresh_seconds=300,
    )

    assert record.levels is None
    assert await quotes.upsert(record) is True
    stored = await quotes.load(market_id)

    assert stored is not None
    assert stored.source is QuoteSource.REALTIME
    assert stored.outcome_bids == ("0.57", "0.39")
    assert stored.outcome_asks == ("0.59", "0.41")
    assert stored.spread == "0.0200"
    assert stored.levels is None
