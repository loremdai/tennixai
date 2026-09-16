"""Executable $10 quotes (T63).

Entry consumes the target outcome's asks; exit consumes the held outcome's
bids. Levels are walked in price priority with the dynamic fee curve from
current market metadata (never hardcoded). Displayed midpoints, last trades
or best levels never substitute for the whole-order quote. Stale books,
insufficient depth and minimum-size violations are not executable.
"""

from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from app.markets.models import (
    ExecutableQuote,
    MarketExecutionMetadata,
    OrderBookState,
    QuoteSide,
)

SHARE_SCALE = Decimal("0.000001")
PRICE_SCALE = Decimal("0.000001")
AVERAGE_SCALE = Decimal("0.000001")
ZERO = Decimal("0")


def _level_fee(
    price: Decimal, shares: Decimal, metadata: MarketExecutionMetadata
) -> Decimal:
    if metadata.fee_rate == 0:
        return ZERO
    base = min(price, Decimal("1") - price)
    factor = Decimal(str(float(base) ** float(metadata.fee_exponent)))
    return metadata.fee_rate * factor * shares


def _walk_levels(
    state: OrderBookState,
    outcome_player_id: str,
    side: QuoteSide,
    *,
    stake: Decimal | None,
    shares_target: Decimal | None,
    metadata: MarketExecutionMetadata,
    market_id: str,
    quoted_at: datetime,
) -> ExecutableQuote | None:
    book = next(
        (item for item in state.books if item.outcome_player_id == outcome_player_id),
        None,
    )
    if book is None:
        return None
    levels = book.asks if side is QuoteSide.ENTRY else book.bids
    if not levels:
        return None

    remaining_stake = stake
    remaining_shares = shares_target
    shares = ZERO
    cost = ZERO
    fee = ZERO
    best_price = levels[0].price

    for level in levels:
        if remaining_stake is not None and remaining_stake <= 0:
            break
        if remaining_shares is not None and remaining_shares <= 0:
            break
        if remaining_stake is not None:
            capacity_cost = level.size * level.price
            take_cost = min(remaining_stake, capacity_cost)
            take_shares = (take_cost / level.price).quantize(
                SHARE_SCALE, rounding=ROUND_HALF_UP
            )
        else:
            assert remaining_shares is not None  # noqa: S101 - one target required
            take_shares = min(remaining_shares, level.size)
            take_cost = (take_shares * level.price).quantize(
                SHARE_SCALE, rounding=ROUND_HALF_UP
            )
        if take_shares <= 0:
            continue
        fee += _level_fee(level.price, take_shares, metadata)
        shares += take_shares
        cost += take_cost
        if remaining_stake is not None:
            remaining_stake -= take_cost
        else:
            remaining_shares = remaining_shares - take_shares

    if shares <= 0:
        return None

    average = (cost / shares).quantize(AVERAGE_SCALE, rounding=ROUND_HALF_UP)
    fee = fee.quantize(SHARE_SCALE, rounding=ROUND_HALF_UP)
    if side is QuoteSide.ENTRY:
        slippage = max(ZERO, average - best_price)
        unfilled = remaining_stake is not None and remaining_stake > 0
    else:
        slippage = max(ZERO, best_price - average)
        unfilled = remaining_shares is not None and remaining_shares > 0
    fillable = not unfilled and not state.is_stale and shares >= metadata.min_order_size
    return ExecutableQuote(
        market_id=market_id,
        outcome_player_id=outcome_player_id,
        side=side,
        stake=cost.quantize(SHARE_SCALE, rounding=ROUND_HALF_UP),
        shares=shares,
        average_price=average,
        fee=fee,
        slippage=slippage.quantize(PRICE_SCALE, rounding=ROUND_HALF_UP),
        is_fillable=fillable,
        book_hash=state.book_hash,
        book_sequence=state.sequence,
        quoted_at=quoted_at,
    )


def compute_quote(
    *,
    state: OrderBookState,
    outcome_player_id: str,
    side: QuoteSide,
    stake: Decimal,
    metadata: MarketExecutionMetadata,
    quoted_at: datetime,
) -> ExecutableQuote | None:
    """Fixed-stake quote walking levels in price priority."""
    return _walk_levels(
        state,
        outcome_player_id,
        side,
        stake=stake,
        shares_target=None,
        metadata=metadata,
        market_id=state.market_id,
        quoted_at=quoted_at,
    )


def compute_exit_quote(
    *,
    state: OrderBookState,
    outcome_player_id: str,
    shares: Decimal,
    metadata: MarketExecutionMetadata,
    quoted_at: datetime,
) -> ExecutableQuote | None:
    """Full-position exit quote against the held outcome's bids."""
    return _walk_levels(
        state,
        outcome_player_id,
        side=QuoteSide.EXIT,
        stake=None,
        shares_target=shares,
        metadata=metadata,
        market_id=state.market_id,
        quoted_at=quoted_at,
    )


def max_acceptable_average_price(
    model_probability: float,
    *,
    min_conservative_net_edge: float,
    fee_rate: Decimal,
    fee_exponent: Decimal,
) -> Decimal:
    """Solve `model - P - fee(P) >= min_edge` for the highest average price.

    Uses the same fee-aware conservative net-edge inequality as the BUY
    gate; never a fixed discount. The result is rounded down to 4 decimals
    so the displayed cap is never looser than the gate.
    """

    def net_edge(price: float) -> float:
        fee = 0.0
        if fee_rate > 0:
            base = min(price, 1.0 - price)
            fee = float(fee_rate) * (base ** float(fee_exponent))
        return model_probability - price - fee - min_conservative_net_edge

    if net_edge(0.01) < 0:
        return Decimal("0")
    low, high = 0.0, 1.0
    for _ in range(80):
        middle = (low + high) / 2
        if net_edge(middle) >= 0:
            low = middle
        else:
            high = middle
    return Decimal(str(low)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
