"""Redis hot state and pub/sub for P3 market books (T60).

An independent namespace from the P2 sports stream: `tnx:p3:*`. Redis is hot
state only — losing it can never create or erase a position, and the worker
rebuilds books from REST. Events carry internal IDs only.
"""

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.markets.models import MarketResolution, OrderBookState


def market_hot_key(market_id: str) -> str:
    return f"tnx:p3:hot:{market_id}"


def market_channel(market_id: str) -> str:
    return f"tnx:p3:market:{market_id}"


def resolution_channel(market_id: str) -> str:
    return f"tnx:p3:resolution:{market_id}"


QUOTE_CATALOG_CHANNEL = "tnx:p3:quotes"
QUOTE_CATALOG_SEQUENCE_KEY = "tnx:p3:quotes:sequence"


class QuoteCatalogPublisher:
    """Global, payload-free invalidation for market-list quote changes."""

    def __init__(self, redis, *, now_fn: Callable[[], datetime] | None = None) -> None:
        self._redis = redis
        self._now = now_fn or (lambda: datetime.now(UTC))

    async def publish_quotes_changed(self, *, count: int) -> dict:
        sequence = await self._redis.incr(QUOTE_CATALOG_SEQUENCE_KEY)
        event = {
            "type": "quotes_changed",
            "sequence": int(sequence),
            "count": count,
            "as_of": self._now().isoformat(),
        }
        await self._redis.publish(QUOTE_CATALOG_CHANNEL, json.dumps(event))
        return event


class MarketHotPublisher:
    def __init__(self, redis, *, now_fn: Callable[[], datetime] | None = None) -> None:
        self._redis = redis
        self._now = now_fn or (lambda: datetime.now(UTC))
        self.events: list[dict] = []

    @staticmethod
    def hot_key(market_id: str) -> str:
        return market_hot_key(market_id)

    @staticmethod
    def channel(market_id: str) -> str:
        return market_channel(market_id)

    async def publish_book(self, market_id: str, state: OrderBookState) -> None:
        event = {
            "type": "market_delta",
            "market_id": market_id,
            "sequence": state.sequence,
            "book_hash": state.book_hash,
            "as_of": state.received_at.isoformat(),
        }
        await self._redis.set(market_hot_key(market_id), state.model_dump_json())
        await self._redis.publish(market_channel(market_id), json.dumps(event))
        self.events.append(event)

    async def publish_gap(self, market_id: str, reason: str) -> None:
        """Stale/gap overlay: the hot snapshot stays as the last trusted
        view; only the overlay event is published."""
        event = {
            "type": "market_gap",
            "market_id": market_id,
            "reason": reason,
            "as_of": self._now().isoformat(),
        }
        await self._redis.publish(market_channel(market_id), json.dumps(event))
        self.events.append(event)

    async def publish_resolution(self, resolution: MarketResolution) -> None:
        event = {
            "type": "resolution_delta",
            **resolution.model_dump(mode="json"),
        }
        await self._redis.publish(
            resolution_channel(resolution.market_id), json.dumps(event)
        )
        self.events.append(event)

    async def get_hot_book(self, market_id: str) -> OrderBookState | None:
        raw = await self._redis.get(market_hot_key(market_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return OrderBookState.model_validate_json(raw)

    async def get_hot_books(
        self, market_ids: Sequence[str]
    ) -> dict[str, OrderBookState]:
        """One MGET for every requested market (T84: no per-row Redis calls).

        Missing keys and unparsable payloads are skipped: absent hot state
        degrades to "not present", never to a fabricated book.
        """
        ids = [market_id for market_id in market_ids if market_id]
        if not ids:
            return {}
        raw_values = await self._redis.mget(
            [market_hot_key(market_id) for market_id in ids]
        )
        books: dict[str, OrderBookState] = {}
        for market_id, raw in zip(ids, raw_values, strict=True):
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            try:
                books[market_id] = OrderBookState.model_validate_json(raw)
            except ValueError:
                continue
        return books
