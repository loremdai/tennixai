"""Canonical display quotes and the durable latest-quote projection (T85).

Two lanes feed one display contract: the realtime lane (strictly mapped,
in-demand markets) supplies a Redis hot book refreshed by the public market
WebSocket; the coverage lane supplies a bounded batch snapshot of every
canonical market. `display_quote` is the single implementation of the seven
visible quote states from the design spec §5.3 — a bare `—` is only ever a
single missing field, never a state, and one outcome's missing side never
hides the other outcome's real quote.

Only internal IDs, decimal level text and timestamps live here. Provider
tokens, condition ids and raw payloads never enter these models.
"""

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, Field

from app.domain import FrozenModel
from app.markets.models import BookLevel, OrderBookState, OutcomeBook

SPREAD_TEXT = Decimal("0.0001")
DEPTH_TEXT = Decimal("0.01")


class QuoteState(StrEnum):
    REALTIME = "realtime"
    SNAPSHOT = "snapshot"
    PARTIAL = "partial"
    NO_LIQUIDITY = "no_liquidity"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    LIMITED = "limited"


class QuoteSource(StrEnum):
    REALTIME = "realtime"
    SNAPSHOT = "snapshot"


class TokenBook(FrozenModel):
    """PRIVATE per-token book from the batch adapter. Never a public DTO."""

    token_id: str = Field(min_length=1)
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()
    book_hash: str = ""
    provider_timestamp: AwareDatetime | None = None


class ClobBooksBatch(FrozenModel):
    """PRIVATE batch result: parsed per-token books plus the raw response."""

    books: Mapping[str, TokenBook] = {}
    missing_tokens: tuple[str, ...] = ()
    malformed_tokens: tuple[str, ...] = ()
    raw: tuple[dict, ...] = ()


class DisplayQuote(FrozenModel):
    """What the pages may show for one market. `as_of` is always the source
    timestamp of the levels that accompany it."""

    state: QuoteState
    source: QuoteSource | None = None
    as_of: AwareDatetime | None = None
    outcome_bids: tuple[str | None, str | None] = (None, None)
    outcome_asks: tuple[str | None, str | None] = (None, None)
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    spread: str | None = None
    depth_usd: str | None = None


class QuoteSnapshotRecord(FrozenModel):
    """One durable latest-quote row (internal IDs only)."""

    market_id: str = Field(min_length=1)
    source: QuoteSource
    state: QuoteState
    book_hash: str | None = None
    as_of: AwareDatetime
    expires_at: AwareDatetime
    levels: tuple[OutcomeBook, OutcomeBook] | None = None
    outcome_bids: tuple[str | None, str | None] = (None, None)
    outcome_asks: tuple[str | None, str | None] = (None, None)
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    spread: str | None = None
    depth_usd: str | None = None


_SOURCE_RANK = {QuoteSource.SNAPSHOT: 1, QuoteSource.REALTIME: 2}


def best_levels(book, outcome_player_id: str | None):
    """(best_bid, best_ask) as (player_id, price text) or None."""
    if book is None:
        return None, None
    side = None
    for candidate in book.books:
        if (
            outcome_player_id is None
            or candidate.outcome_player_id == outcome_player_id
        ):
            side = candidate
            break
    if side is None:
        return None, None
    best_bid = (side.outcome_player_id, str(side.bids[0].price)) if side.bids else None
    best_ask = (side.outcome_player_id, str(side.asks[0].price)) if side.asks else None
    return best_bid, best_ask


def outcome_levels(book, outcome_ids):
    """Per-outcome top levels aligned to outcome_ids, plus mean spread and
    top-of-book notional depth. Missing sides stay None."""
    if book is None:
        return None, None, None, None
    by_player = {side.outcome_player_id: side for side in book.books}
    bids: list[str | None] = []
    asks: list[str | None] = []
    spreads: list = []
    depth = Decimal("0")
    for player_id in outcome_ids:
        side = by_player.get(player_id) if player_id else None
        if side is None:
            bids.append(None)
            asks.append(None)
            continue
        bid = str(side.bids[0].price) if side.bids else None
        ask = str(side.asks[0].price) if side.asks else None
        bids.append(bid)
        asks.append(ask)
        if side.bids:
            depth += side.bids[0].price * side.bids[0].size
        if side.asks:
            depth += side.asks[0].price * side.asks[0].size
        if bid is not None and ask is not None:
            spreads.append(Decimal(ask) - Decimal(bid))
    spread = (
        (sum(spreads) / Decimal(len(spreads))).quantize(SPREAD_TEXT)
        if spreads
        else None
    )
    return (
        (bids[0], bids[1]) if len(bids) == 2 else None,
        (asks[0], asks[1]) if len(asks) == 2 else None,
        spread,
        depth.quantize(DEPTH_TEXT) if (spreads or depth) else None,
    )


def _completeness(books: Sequence[OutcomeBook]) -> str:
    """How many sides carry displayable levels: both | one | none.

    Callers map this onto their own lane's state name, so a fresh WebSocket
    book reads `realtime` and a batch snapshot reads `snapshot`, while a
    one-sided book is `partial` in either lane.
    """
    sides = [bool(side.bids or side.asks) for side in books]
    if all(sides):
        return "both"
    if any(sides):
        return "one"
    return "none"


def _lane_state(books: Sequence[OutcomeBook], *, complete: QuoteState) -> QuoteState:
    completeness = _completeness(books)
    if completeness == "both":
        return complete
    if completeness == "one":
        return QuoteState.PARTIAL
    return QuoteState.NO_LIQUIDITY


def _is_fresh(stamp: datetime, now: datetime, bound_seconds: int) -> bool:
    return now - stamp <= timedelta(seconds=bound_seconds)


def _record_from_books(
    *,
    market_id: str,
    source: QuoteSource,
    state: QuoteState,
    books: tuple[OutcomeBook, OutcomeBook],
    book_hash: str | None,
    as_of: datetime,
    expires_at: datetime,
) -> QuoteSnapshotRecord:
    book_state = OrderBookState(
        market_id=market_id,
        books=books,
        sequence=0,
        book_hash=book_hash or "batch",
        provider_timestamp=as_of,
        received_at=as_of,
    )
    outcome_ids = tuple(side.outcome_player_id for side in books)
    bids, asks, spread, depth = outcome_levels(book_state, outcome_ids)
    best_bid, best_ask = best_levels(book_state, outcome_ids[0])
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=source,
        state=state,
        book_hash=book_hash,
        as_of=as_of,
        expires_at=expires_at,
        levels=(books[0], books[1]),
        outcome_bids=bids or (None, None),
        outcome_asks=asks or (None, None),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=str(spread) if spread is not None else None,
        depth_usd=str(depth) if depth is not None else None,
    )


def display_quote(
    *,
    hot_book: OrderBookState | None,
    snapshot: QuoteSnapshotRecord | None,
    now: datetime,
    realtime_fresh_seconds: int,
    snapshot_fresh_seconds: int,
) -> DisplayQuote:
    """Single source of truth for the visible quote state (spec §5.3).

    A fresh WebSocket book always wins; otherwise the durable snapshot is
    shown with its own state, upgraded to `stale` once it outlives its own
    lane's freshness bound (realtime for a WebSocket-sourced quote, the
    coverage window for a batch snapshot). Nothing is ever fabricated: with
    neither source the state is `unavailable`, not a zero quote.
    """
    if (
        hot_book is not None
        and not hot_book.is_stale
        and _is_fresh(hot_book.received_at, now, realtime_fresh_seconds)
    ):
        state = _lane_state(hot_book.books, complete=QuoteState.REALTIME)
        bids, asks, spread, depth = outcome_levels(
            hot_book, [side.outcome_player_id for side in hot_book.books]
        )
        best_bid, best_ask = best_levels(hot_book, hot_book.books[0].outcome_player_id)
        return DisplayQuote(
            state=state,
            source=QuoteSource.REALTIME,
            as_of=hot_book.received_at,
            outcome_bids=bids or (None, None),
            outcome_asks=asks or (None, None),
            best_bid=best_bid,
            best_ask=best_ask,
            spread=str(spread) if spread is not None else None,
            depth_usd=str(depth) if depth is not None else None,
        )
    if snapshot is None:
        return DisplayQuote(state=QuoteState.UNAVAILABLE)
    # A WebSocket-sourced quote ages out at the realtime bound, a batch
    # snapshot at the coverage bound: the slower window must never vouch for
    # a quote that was only ever valid for a moment.
    bound = (
        realtime_fresh_seconds
        if snapshot.source is QuoteSource.REALTIME
        else snapshot_fresh_seconds
    )
    state = (
        snapshot.state if _is_fresh(snapshot.as_of, now, bound) else QuoteState.STALE
    )
    return DisplayQuote(
        state=state,
        source=snapshot.source,
        as_of=snapshot.as_of,
        outcome_bids=snapshot.outcome_bids,
        outcome_asks=snapshot.outcome_asks,
        best_bid=snapshot.best_bid,
        best_ask=snapshot.best_ask,
        spread=snapshot.spread,
        depth_usd=snapshot.depth_usd,
    )


def build_quote_snapshot(
    *,
    market_id: str,
    token_ids: tuple[str, str],
    player_ids: tuple[str | None, str | None],
    batch: ClobBooksBatch,
    observed_at: datetime,
    expires_at: datetime,
) -> QuoteSnapshotRecord:
    """Canonical two-outcome projection from a private token batch.

    Exactly one token may be absent or malformed without discarding the
    other side: the state becomes `partial` (with the parsed side's real
    levels) when that side has any level, `unavailable` when it does not.
    Unresolved listings retain their supplier-ordered prices without
    manufacturing outcome/player identities or `OutcomeBook` records.
    """
    parsed = [batch.books.get(token_id) for token_id in token_ids]
    if any(not player_id for player_id in player_ids):
        present = sum(token_book is not None for token_book in parsed)
        has_levels = [
            token_book is not None and bool(token_book.bids or token_book.asks)
            for token_book in parsed
        ]
        if present == 2:
            state = (
                QuoteState.SNAPSHOT
                if all(has_levels)
                else QuoteState.PARTIAL
                if any(has_levels)
                else QuoteState.NO_LIQUIDITY
            )
        elif any(has_levels):
            state = QuoteState.PARTIAL
        else:
            state = QuoteState.UNAVAILABLE

        bids = tuple(
            str(book.bids[0].price) if book is not None and book.bids else None
            for book in parsed
        )
        asks = tuple(
            str(book.asks[0].price) if book is not None and book.asks else None
            for book in parsed
        )
        spreads = [
            book.asks[0].price - book.bids[0].price
            for book in parsed
            if book is not None and book.bids and book.asks
        ]
        depth = sum(
            (
                book.bids[0].price * book.bids[0].size
                if book is not None and book.bids
                else Decimal("0")
            )
            + (
                book.asks[0].price * book.asks[0].size
                if book is not None and book.asks
                else Decimal("0")
            )
            for book in parsed
        )
        hashes = [book.book_hash for book in parsed if book is not None]
        book_hash = (
            hashlib.sha256(":".join(hashes).encode("utf-8")).hexdigest()
            if hashes
            else None
        )
        return QuoteSnapshotRecord(
            market_id=market_id,
            source=QuoteSource.SNAPSHOT,
            state=state,
            book_hash=book_hash,
            as_of=observed_at,
            expires_at=expires_at,
            outcome_bids=bids,
            outcome_asks=asks,
            spread=(
                str((sum(spreads) / Decimal(len(spreads))).quantize(SPREAD_TEXT))
                if spreads
                else None
            ),
            depth_usd=str(depth.quantize(DEPTH_TEXT)) if depth else None,
        )

    books = tuple(
        OutcomeBook(
            outcome_player_id=player_id,
            bids=token_book.bids if token_book is not None else (),
            asks=token_book.asks if token_book is not None else (),
        )
        for token_book, player_id in zip(parsed, player_ids, strict=True)
    )
    hashes = [token_book.book_hash for token_book in parsed if token_book is not None]
    book_hash = (
        hashlib.sha256(":".join(hashes).encode("utf-8")).hexdigest() if hashes else None
    )
    present = sum(1 for token_book in parsed if token_book is not None)
    if present == 2:
        state = _lane_state(books, complete=QuoteState.SNAPSHOT)
    elif present == 1:
        state = (
            QuoteState.PARTIAL
            if any(side.bids or side.asks for side in books)
            else QuoteState.UNAVAILABLE
        )
    else:
        state = QuoteState.UNAVAILABLE
    if state is QuoteState.UNAVAILABLE:
        return QuoteSnapshotRecord(
            market_id=market_id,
            source=QuoteSource.SNAPSHOT,
            state=state,
            book_hash=book_hash,
            as_of=observed_at,
            expires_at=expires_at,
        )
    return _record_from_books(
        market_id=market_id,
        source=QuoteSource.SNAPSHOT,
        state=state,
        books=(books[0], books[1]),
        book_hash=book_hash,
        as_of=observed_at,
        expires_at=expires_at,
    )


def realtime_quote_record(
    book: OrderBookState, *, fresh_seconds: int
) -> QuoteSnapshotRecord:
    """Mirror a fresh WebSocket hot book into the shared projection.

    Used by the runtime's realtime mirror so pages read ONE precedence rule
    for both lanes; the record never carries provider identity.
    """
    return _record_from_books(
        market_id=book.market_id,
        source=QuoteSource.REALTIME,
        state=_lane_state(book.books, complete=QuoteState.REALTIME),
        books=(book.books[0], book.books[1]),
        book_hash=book.book_hash,
        as_of=book.received_at,
        expires_at=book.received_at + timedelta(seconds=fresh_seconds),
    )


def realtime_listing_quote_record(
    *,
    market_id: str,
    outcome_bids: tuple[str | None, str | None],
    outcome_asks: tuple[str | None, str | None],
    as_of: datetime,
    fresh_seconds: int,
) -> QuoteSnapshotRecord:
    """Persist supplier-ordered best quotes without inventing player IDs."""
    spreads = [
        Decimal(ask) - Decimal(bid)
        for bid, ask in zip(outcome_bids, outcome_asks, strict=True)
        if bid is not None and ask is not None
    ]
    has_values = [
        bid is not None or ask is not None
        for bid, ask in zip(outcome_bids, outcome_asks, strict=True)
    ]
    state = (
        QuoteState.REALTIME
        if all(has_values)
        else QuoteState.PARTIAL
        if any(has_values)
        else QuoteState.NO_LIQUIDITY
    )
    spread = (
        (sum(spreads) / Decimal(len(spreads))).quantize(SPREAD_TEXT)
        if spreads
        else None
    )
    content = ":".join(
        f"{bid or ''}/{ask or ''}"
        for bid, ask in zip(outcome_bids, outcome_asks, strict=True)
    )
    return QuoteSnapshotRecord(
        market_id=market_id,
        source=QuoteSource.REALTIME,
        state=state,
        book_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        as_of=as_of,
        expires_at=as_of + timedelta(seconds=fresh_seconds),
        outcome_bids=outcome_bids,
        outcome_asks=outcome_asks,
        spread=str(spread) if spread is not None else None,
    )


def decide_quote_write(
    existing: QuoteSnapshotRecord | None, incoming: QuoteSnapshotRecord
) -> bool:
    """Precedence rule for the shared projection (spec §5.2).

    Only newer content may replace stored content; at the same instant the
    realtime lane may take over the snapshot lane but never the reverse, and
    a byte-identical rerun writes nothing (idempotent).
    """
    if existing is None:
        return True
    if incoming.as_of < existing.as_of:
        return False
    if incoming.as_of == existing.as_of:
        if (
            incoming.book_hash == existing.book_hash
            and incoming.state is existing.state
            and incoming.source is existing.source
        ):
            return False
        return _SOURCE_RANK[incoming.source] >= _SOURCE_RANK[existing.source]
    return True


__all__ = [
    "ClobBooksBatch",
    "DisplayQuote",
    "QuoteSnapshotRecord",
    "QuoteSource",
    "QuoteState",
    "TokenBook",
    "best_levels",
    "build_quote_snapshot",
    "decide_quote_write",
    "display_quote",
    "outcome_levels",
    "realtime_listing_quote_record",
    "realtime_quote_record",
]
