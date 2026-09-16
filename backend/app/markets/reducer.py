"""Canonical market book reducer (T60).

Single writer per market. Full books replace state, price changes mutate
exact levels, zero size deletes a level, timestamp/hash regressions are
rejected, tick changes only update metadata and a reconnect always rebuilds
the baseline from REST before deltas are accepted again. The reducer is pure
in-memory state; durable evidence is written elsewhere in bounded batches.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.markets.models import BookLevel, OrderBookState, OutcomeBook


@dataclass(frozen=True)
class RawMarketEvent:
    """One parsed wire message from the public market channel."""

    event_type: str
    asset_id: str
    payload: dict[str, Any]
    received_at: datetime


@dataclass(frozen=True)
class BookReduction:
    market_id: str
    changed: bool
    rejected: str | None = None
    needs_snapshot: bool = False
    tick_size: Decimal | None = None
    resolution_requested: bool = False
    malformed: str | None = None


def _parse_epoch_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@dataclass
class _TokenState:
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    last_hash: str | None = None
    last_timestamp: datetime | None = None
    tick_size: Decimal | None = None
    has_baseline: bool = False


class MarketBookReducer:
    def __init__(
        self,
        *,
        market_id: str,
        token_players: dict[str, str],
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._market_id = market_id
        self._token_players = dict(token_players)
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._tokens: dict[str, _TokenState] = {
            token: _TokenState() for token in token_players
        }
        self._sequence = 0

    @property
    def market_id(self) -> str:
        return self._market_id

    def current_tick_size(self, token_id: str) -> Decimal | None:
        state = self._tokens.get(token_id)
        return state.tick_size if state is not None else None

    def current_state(self) -> OrderBookState | None:
        """Canonical both-sides state, or None until every token has a
        baseline."""
        if not all(state.has_baseline for state in self._tokens.values()):
            return None
        books: list[OutcomeBook] = []
        hashes: list[str] = []
        timestamps: list[datetime] = []
        for token, player_id in self._token_players.items():
            state = self._tokens[token]
            bids = tuple(
                BookLevel(price=price, size=size)
                for price, size in sorted(state.bids.items(), reverse=True)
            )
            asks = tuple(
                BookLevel(price=price, size=size)
                for price, size in sorted(state.asks.items())
            )
            books.append(OutcomeBook(outcome_player_id=player_id, bids=bids, asks=asks))
            if state.last_hash:
                hashes.append(state.last_hash)
            else:
                digest = hashlib.sha256(
                    "|".join(
                        f"{price}:{size}" for price, size in sorted(state.bids.items())
                    ).encode("utf-8")
                    + b"/"
                    + "|".join(
                        f"{price}:{size}" for price, size in sorted(state.asks.items())
                    ).encode("utf-8")
                ).hexdigest()[:16]
                hashes.append(digest)
            if state.last_timestamp is not None:
                timestamps.append(state.last_timestamp)
        combined = hashlib.sha256(
            f"{self._sequence}:{':'.join(hashes)}".encode("utf-8")
        ).hexdigest()
        now = self._now()
        return OrderBookState(
            market_id=self._market_id,
            books=(books[0], books[1]),
            sequence=self._sequence,
            book_hash=combined,
            provider_timestamp=max(timestamps) if timestamps else now,
            received_at=now,
        )

    def baseline_from_rest(
        self, state: OrderBookState, player_tokens: dict[str, str]
    ) -> BookReduction:
        """Rebuild the trusted baseline from a REST snapshot. Always used on
        initial subscribe and after any reconnect before deltas resume."""
        self._token_players = {
            player_tokens[book.outcome_player_id]: book.outcome_player_id
            for book in state.books
        }
        for token in self._token_players:
            if token not in self._tokens:
                self._tokens[token] = _TokenState()
        for book in state.books:
            token = player_tokens[book.outcome_player_id]
            token_state = self._tokens[token]
            token_state.bids = {level.price: level.size for level in book.bids}
            token_state.asks = {level.price: level.size for level in book.asks}
            token_state.last_hash = f"{state.book_hash}:{token}"
            token_state.last_timestamp = state.provider_timestamp
            token_state.has_baseline = True
        self._sequence = state.sequence
        return BookReduction(market_id=self._market_id, changed=True)

    def apply_event(self, event: RawMarketEvent) -> BookReduction:
        token = event.asset_id
        state = self._tokens.get(token)
        if state is None:
            return BookReduction(
                market_id=self._market_id, changed=False, rejected="unknown_asset"
            )
        payload = event.payload

        if event.event_type == "book":
            rejection = self._check_regression(
                state,
                _parse_epoch_ms(payload.get("timestamp")),
                payload.get("hash"),
            )
            if rejection is not None:
                return BookReduction(
                    market_id=self._market_id, changed=False, rejected=rejection
                )
            buys = payload.get("buys")
            if buys is None:
                buys = payload.get("bids", [])
            sells = payload.get("sells")
            if sells is None:
                sells = payload.get("asks", [])
            bids, malformed = self._parse_levels(buys)
            if malformed is not None:
                return BookReduction(
                    market_id=self._market_id, changed=False, malformed=malformed
                )
            asks, malformed = self._parse_levels(sells)
            if malformed is not None:
                return BookReduction(
                    market_id=self._market_id, changed=False, malformed=malformed
                )
            state.bids = bids
            state.asks = asks
            state.has_baseline = True
            self._record_marker(state, payload)
            self._sequence += 1
            return BookReduction(market_id=self._market_id, changed=True)

        if event.event_type == "price_change":
            if not state.has_baseline:
                return BookReduction(
                    market_id=self._market_id, changed=False, needs_snapshot=True
                )
            rejection = self._check_regression(
                state,
                _parse_epoch_ms(payload.get("timestamp")),
                payload.get("hash"),
            )
            if rejection is not None:
                return BookReduction(
                    market_id=self._market_id, changed=False, rejected=rejection
                )
            levels_changed = False
            for change in payload.get("changes", []):
                if not isinstance(change, dict):
                    continue
                price = _parse_decimal(change.get("price"))
                size = _parse_decimal(change.get("size"))
                side = str(change.get("side", "")).upper()
                if price is None or size is None or side not in ("BUY", "SELL"):
                    return BookReduction(
                        market_id=self._market_id,
                        changed=False,
                        malformed="price_change_level",
                    )
                book = state.bids if side == "BUY" else state.asks
                if size == 0:
                    if book.pop(price, None) is not None:
                        levels_changed = True
                elif book.get(price) != size:
                    book[price] = size
                    levels_changed = True
            self._record_marker(state, payload)
            if not levels_changed:
                return BookReduction(market_id=self._market_id, changed=False)
            self._sequence += 1
            return BookReduction(market_id=self._market_id, changed=True)

        if event.event_type == "tick_size_change":
            tick = _parse_decimal(payload.get("new_tick_size"))
            if tick is not None:
                state.tick_size = tick
            return BookReduction(
                market_id=self._market_id, changed=False, tick_size=tick
            )

        if event.event_type == "resolution":
            return BookReduction(
                market_id=self._market_id, changed=False, resolution_requested=True
            )

        return BookReduction(market_id=self._market_id, changed=False)

    @staticmethod
    def _check_regression(
        state: _TokenState, timestamp: datetime | None, book_hash: Any
    ) -> str | None:
        if book_hash and state.last_hash == str(book_hash):
            return "duplicate_hash"
        if (
            timestamp is not None
            and state.last_timestamp is not None
            and timestamp < state.last_timestamp
        ):
            return "stale_timestamp"
        return None

    @staticmethod
    def _record_marker(state: _TokenState, payload: dict[str, Any]) -> None:
        book_hash = payload.get("hash")
        if book_hash:
            state.last_hash = str(book_hash)
        timestamp = _parse_epoch_ms(payload.get("timestamp"))
        if timestamp is not None:
            state.last_timestamp = timestamp

    @staticmethod
    def _parse_levels(
        raw_levels: Any,
    ) -> tuple[dict[Decimal, Decimal], str | None]:
        levels: dict[Decimal, Decimal] = {}
        if not isinstance(raw_levels, list):
            return {}, "levels_not_list"
        for raw in raw_levels:
            if not isinstance(raw, dict):
                return {}, "level_not_object"
            price = _parse_decimal(raw.get("price"))
            size = _parse_decimal(raw.get("size"))
            if price is None or size is None or price <= 0 or size < 0:
                return {}, "level_value"
            if price in levels:
                return {}, "duplicate_level"
            if size > 0:
                levels[price] = size
        return levels, None
