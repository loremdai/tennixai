"""Latest-quote projection schema and canonical quote display tests (T85)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.markets.models import BookLevel, OrderBookState, OutcomeBook
from app.markets.quotes import (
    ClobBooksBatch,
    QuoteSnapshotRecord,
    QuoteSource,
    QuoteState,
    TokenBook,
    build_quote_snapshot,
    decide_quote_write,
    display_quote,
    realtime_quote_record,
)
from app.persistence.models import Base, MarketQuoteSnapshotRow

NOW = datetime(2026, 9, 22, 8, 0, tzinfo=UTC)


def test_market_quote_snapshots_table_shape():
    table = Base.metadata.tables["market_quote_snapshots"]
    assert MarketQuoteSnapshotRow.__tablename__ == "market_quote_snapshots"
    assert [column.name for column in table.primary_key.columns] == ["market_id"]
    for name in (
        "source",
        "quote_state",
        "book_hash",
        "as_of",
        "expires_at",
        "payload",
        "updated_at",
    ):
        assert name in table.columns
    # Display statistics are stored explicitly so a missing side is a NULL
    # column, never a fabricated zero.
    for name in (
        "outcome_a_bid",
        "outcome_a_ask",
        "outcome_b_bid",
        "outcome_b_ask",
        "spread",
        "depth_usd",
    ):
        assert name in table.columns
        assert table.columns[name].nullable
    for name in ("as_of", "expires_at", "updated_at"):
        assert table.columns[name].type.timezone
    # Provider identity never enters the projection.
    for name in ("token", "condition_id", "provider_event_id"):
        assert all(name not in column.name for column in table.columns)


def outcome_book(player_id: str, *, bid: str | None, ask: str | None) -> OutcomeBook:
    return OutcomeBook(
        outcome_player_id=player_id,
        bids=(BookLevel(price=Decimal(bid), size=Decimal("100")),) if bid else (),
        asks=(BookLevel(price=Decimal(ask), size=Decimal("100")),) if ask else (),
    )


def hot_book(
    *,
    a: tuple[str | None, str | None],
    b: tuple[str | None, str | None],
    received_at: datetime = NOW,
    is_stale: bool = False,
) -> OrderBookState:
    return OrderBookState(
        market_id="mkt_1",
        books=(
            outcome_book("ply_a", bid=a[0], ask=a[1]),
            outcome_book("ply_b", bid=b[0], ask=b[1]),
        ),
        sequence=5,
        book_hash="ws_hash",
        provider_timestamp=received_at,
        received_at=received_at,
        is_stale=is_stale,
    )


def snapshot_record(
    *,
    state: QuoteState = QuoteState.SNAPSHOT,
    source: QuoteSource = QuoteSource.SNAPSHOT,
    as_of: datetime = NOW,
    book_hash: str | None = "snap_hash",
) -> QuoteSnapshotRecord:
    return QuoteSnapshotRecord(
        market_id="mkt_1",
        source=source,
        state=state,
        book_hash=book_hash,
        as_of=as_of,
        expires_at=as_of + timedelta(seconds=300),
        outcome_bids=("0.58", "0.40"),
        outcome_asks=("0.60", "0.42"),
        best_bid=("ply_a", "0.58"),
        best_ask=("ply_a", "0.60"),
        spread="0.0200",
        depth_usd="306.00",
    )


def test_display_quote_prefers_a_fresh_realtime_book():
    quote = display_quote(
        hot_book=hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")),
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=2),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.REALTIME
    assert quote.source is QuoteSource.REALTIME
    assert quote.outcome_asks == ("0.63", "0.39")
    assert quote.as_of == NOW


def test_display_quote_falls_back_to_the_snapshot_when_hot_state_is_old():
    quote = display_quote(
        hot_book=hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")),
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=30),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.SNAPSHOT
    assert quote.source is QuoteSource.SNAPSHOT
    assert quote.outcome_asks == ("0.60", "0.42")


def test_display_quote_marks_an_expired_snapshot_stale_and_keeps_last_trusted_levels():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(),
        now=NOW + timedelta(seconds=301),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.STALE
    assert quote.as_of == NOW
    assert quote.outcome_bids == ("0.58", "0.40")


def test_display_quote_without_any_source_is_unavailable_not_zero():
    quote = display_quote(
        hot_book=None,
        snapshot=None,
        now=NOW,
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.UNAVAILABLE
    assert quote.source is None and quote.as_of is None
    assert quote.outcome_bids == (None, None)
    assert quote.best_bid is None and quote.depth_usd is None


def test_display_quote_reports_one_sided_books_as_partial():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(state=QuoteState.PARTIAL),
        now=NOW,
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.PARTIAL
    # One outcome's real ask never hides the other outcome's missing ask.
    assert quote.outcome_asks == ("0.60", "0.42")


def test_display_quote_keeps_limited_state_with_the_last_trusted_time():
    quote = display_quote(
        hot_book=None,
        snapshot=snapshot_record(state=QuoteState.LIMITED),
        now=NOW + timedelta(seconds=10),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert quote.state is QuoteState.LIMITED
    assert quote.as_of == NOW
    assert quote.outcome_asks == ("0.60", "0.42")


def test_build_quote_snapshot_classifies_both_sides_partial_and_empty():
    tokens = ("tok_a", "tok_b")
    players = ("ply_a", "ply_b")
    both = ClobBooksBatch(
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
        market_id="mkt_1",
        token_ids=tokens,
        player_ids=players,
        batch=both,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert record.state is QuoteState.SNAPSHOT
    assert record.outcome_asks == ("0.60", "0.42")
    assert record.best_bid == ("ply_a", "0.58")
    assert record.book_hash is not None and len(record.book_hash) == 64
    assert len(record.levels or ()) == 2

    one_sided = ClobBooksBatch(
        books={
            "tok_a": TokenBook(
                token_id="tok_a",
                bids=(),
                asks=(BookLevel(price=Decimal("0.60"), size=Decimal("10")),),
                book_hash="ha",
                provider_timestamp=NOW,
            ),
            "tok_b": TokenBook(
                token_id="tok_b",
                bids=(),
                asks=(),
                book_hash="hb",
                provider_timestamp=NOW,
            ),
        },
        missing_tokens=(),
        malformed_tokens=(),
        raw=(),
    )
    partial = build_quote_snapshot(
        market_id="mkt_1",
        token_ids=tokens,
        player_ids=players,
        batch=one_sided,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert partial.state is QuoteState.PARTIAL
    assert partial.outcome_asks == ("0.60", None)

    empty = ClobBooksBatch(
        books={
            "tok_a": TokenBook(
                token_id="tok_a",
                bids=(),
                asks=(),
                book_hash="ha",
                provider_timestamp=NOW,
            ),
            "tok_b": TokenBook(
                token_id="tok_b",
                bids=(),
                asks=(),
                book_hash="hb",
                provider_timestamp=NOW,
            ),
        },
        missing_tokens=(),
        malformed_tokens=(),
        raw=(),
    )
    none_state = build_quote_snapshot(
        market_id="mkt_1",
        token_ids=tokens,
        player_ids=players,
        batch=empty,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert none_state.state is QuoteState.NO_LIQUIDITY
    assert none_state.outcome_asks == (None, None)

    unavailable = build_quote_snapshot(
        market_id="mkt_1",
        token_ids=tokens,
        player_ids=players,
        batch=ClobBooksBatch(
            books={}, missing_tokens=tokens, malformed_tokens=(), raw=()
        ),
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=300),
    )
    assert unavailable.state is QuoteState.UNAVAILABLE
    assert unavailable.levels is None


def test_decide_quote_write_precedence_truth_table():
    current = snapshot_record(as_of=NOW)
    assert decide_quote_write(None, current) is True
    # Older never overwrites newer.
    older = snapshot_record(as_of=NOW - timedelta(seconds=1), book_hash="other")
    assert decide_quote_write(current, older) is False
    # Byte-identical rerun is idempotent.
    assert decide_quote_write(current, snapshot_record(as_of=NOW)) is False
    # Same instant: the realtime lane may take over, the snapshot lane may not.
    ws = snapshot_record(
        source=QuoteSource.REALTIME,
        state=QuoteState.REALTIME,
        as_of=NOW,
        book_hash="ws",
    )
    assert decide_quote_write(current, ws) is True
    assert (
        decide_quote_write(ws, snapshot_record(as_of=NOW, book_hash="newer_snapshot"))
        is False
    )
    # Newer always wins.
    assert (
        decide_quote_write(
            current, snapshot_record(as_of=NOW + timedelta(seconds=1), book_hash="next")
        )
        is True
    )


def test_realtime_quote_record_mirrors_levels_with_precedence_metadata():
    record = realtime_quote_record(
        hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")), fresh_seconds=300
    )
    assert record.source is QuoteSource.REALTIME
    assert record.state is QuoteState.REALTIME
    assert record.as_of == NOW
    assert record.expires_at == NOW + timedelta(seconds=300)
    assert record.outcome_asks == ("0.63", "0.39")


def test_a_stored_realtime_quote_ages_out_at_the_realtime_bound():
    """A WebSocket-sourced quote is never vouched for by the snapshot window:
    once it is older than the realtime bound it reads as expired."""
    record = realtime_quote_record(
        hot_book(a=("0.61", "0.63"), b=("0.37", "0.39")), fresh_seconds=5
    )
    within = display_quote(
        hot_book=None,
        snapshot=record,
        now=NOW + timedelta(seconds=2),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert within.state is QuoteState.REALTIME
    assert within.source is QuoteSource.REALTIME
    assert within.outcome_asks == ("0.63", "0.39")

    aged_out = display_quote(
        hot_book=None,
        snapshot=record,
        now=NOW + timedelta(seconds=6),
        realtime_fresh_seconds=5,
        snapshot_fresh_seconds=300,
    )
    assert aged_out.state is QuoteState.STALE
    assert aged_out.source is QuoteSource.REALTIME
    assert aged_out.outcome_asks == ("0.63", "0.39")  # last trusted levels kept
