"""Redis hot state and pub/sub for P3 market books (T60).

An independent namespace from the P2 sports stream: `tnx:p3:*`. Redis is hot
state only — losing it can never create or erase a position, and the worker
rebuilds books from REST. Events carry internal IDs only.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

from app.markets.models import OrderBookState


def market_hot_key(market_id: str) -> str:
    return f"tnx:p3:hot:{market_id}"


def market_channel(market_id: str) -> str:
    return f"tnx:p3:market:{market_id}"


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

    async def get_hot_book(self, market_id: str) -> OrderBookState | None:
        raw = await self._redis.get(market_hot_key(market_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return OrderBookState.model_validate_json(raw)
