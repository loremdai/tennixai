"""Executable $10 quote tests (T63).

Entry consumes the target outcome's asks, exit consumes the held outcome's
bids; levels are walked in price priority with the dynamic fee curve;
insufficient depth, stale books and minimum-size violations are not
executable; both outcome books stay independent (no forced complement).
"""

from datetime import UTC, datetime
from decimal import Decimal


from app.decision.quotes import compute_quote
from app.markets.models import (
    BookLevel,
    ExecutableQuote,
    MarketExecutionMetadata,
    OrderBookState,
    OutcomeBook,
    QuoteSide,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def metadata(
    *,
    fee_rate: str = "0",
    fee_exponent: str = "1",
    taker_only: bool = True,
    min_order_size: str = "5",
    tick_size: str = "0.01",
    delay: int = 10,
) -> MarketExecutionMetadata:
    return MarketExecutionMetadata(
        market_id="mkt_q",
        tick_size=Decimal(tick_size),
        min_order_size=Decimal(min_order_size),
        fee_rate=Decimal(fee_rate),
        fee_exponent=Decimal(fee_exponent),
        taker_only=taker_only,
        maker_base_fee=Decimal("0"),
        taker_base_fee=Decimal("0"),
        sports_delay_seconds=delay,
        game_start_time=NOW,
        fetched_at=NOW,
    )


def state(
    *,
    asks_a=(("0.50", "10"), ("0.55", "100")),
    bids_a=(("0.45", "50"), ("0.40", "100")),
    asks_b=(("0.50", "100"),),
    bids_b=(("0.45", "100"),),
    stale: bool = False,
    book_hash: str = "book_v7",
) -> OrderBookState:
    def levels(raw) -> tuple[BookLevel, ...]:
        return tuple(
            BookLevel(price=Decimal(price), size=Decimal(size)) for price, size in raw
        )

    return OrderBookState(
        market_id="mkt_q",
        books=(
            OutcomeBook(
                outcome_player_id="ply_a", bids=levels(bids_a), asks=levels(asks_a)
            ),
            OutcomeBook(
                outcome_player_id="ply_b", bids=levels(bids_b), asks=levels(asks_b)
            ),
        ),
        sequence=7,
        book_hash=book_hash,
        provider_timestamp=NOW,
        received_at=NOW,
        is_stale=stale,
    )


def entry(**overrides) -> ExecutableQuote | None:
    params = {
        "state": state(),
        "outcome_player_id": "ply_a",
        "side": QuoteSide.ENTRY,
        "stake": Decimal("10.00"),
        "metadata": metadata(),
        "quoted_at": NOW,
    }
    params.update(overrides)
    return compute_quote(**params)


def test_single_level_walk_is_exact():
    quote = entry(state=state(asks_a=(("0.50", "100"),)))

    assert quote is not None
    assert quote.stake == Decimal("10.00")
    assert quote.shares == Decimal("20")
    assert quote.average_price == Decimal("0.5")
    assert quote.fee == Decimal("0")
    assert quote.slippage == Decimal("0")
    assert quote.is_fillable
    assert quote.book_hash == "book_v7"
    assert quote.book_sequence == 7


def test_multi_level_walk_uses_price_priority_and_exact_decimal_rounding():
    quote = entry()

    assert quote is not None
    # $5 at 0.50 (10 shares) + $5 at 0.55 (9.090909 shares).
    assert quote.shares == Decimal("19.090909")
    assert quote.average_price == Decimal("0.523810")
    assert quote.slippage == Decimal("0.023810")
    assert quote.is_fillable


def test_dynamic_fee_curve_charges_min_price_exponent_per_level():
    quote = entry(metadata=metadata(fee_rate="0.02", fee_exponent="2"))

    assert quote is not None
    # Level 1: 10 shares * 0.02 * min(0.5,0.5)^2 = 0.05
    # Level 2: 9.090909 shares * 0.02 * min(0.55,0.45)^2 = 0.036818...
    assert quote.fee == Decimal("0.086818")


def test_insufficient_depth_is_not_fillable():
    quote = entry(state=state(asks_a=(("0.50", "4"),)))

    assert quote is not None
    assert not quote.is_fillable
    # Only 4 shares ($2 of the $10 stake) found depth.
    assert quote.shares == Decimal("4")


def test_empty_side_returns_no_quote():
    assert entry(state=state(asks_a=())) is None


def test_stale_book_quote_is_never_fillable():
    quote = entry(state=state(stale=True))

    assert quote is not None
    assert not quote.is_fillable


def test_minimum_order_size_violation_is_not_fillable():
    quote = entry(
        state=state(asks_a=(("0.50", "8"),)), metadata=metadata(min_order_size="10")
    )

    assert quote is not None
    assert not quote.is_fillable


def test_exit_quote_consumes_bids_of_the_held_outcome():
    quote = compute_quote(
        state=state(),
        outcome_player_id="ply_a",
        side=QuoteSide.EXIT,
        stake=Decimal("10.00"),
        metadata=metadata(),
        quoted_at=NOW,
    )

    assert quote is not None
    assert quote.side is QuoteSide.EXIT
    # Bids walk descending: 0.45 first (50 shares capacity = $22.50).
    assert quote.average_price == Decimal("0.45")
    assert quote.shares == Decimal("22.222222")
    assert quote.is_fillable


def test_both_outcome_books_stay_independent():
    # Drastically changing ply_b's book must not alter ply_a's entry quote.
    baseline = entry()
    changed = entry(state=state(asks_b=(("0.99", "1"),), bids_b=(("0.01", "1"),)))

    assert baseline is not None and changed is not None
    assert baseline.average_price == changed.average_price
    assert baseline.shares == changed.shares
