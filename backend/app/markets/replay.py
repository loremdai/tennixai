"""Deterministic market replay feed (T60/T70).

Reads a sanitized JSONL fixture and replays typed raw market events with
controlled pacing. Identical fixtures must produce identical canonical
output; the feed never touches the network.
"""

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path

import asyncio

from app.markets.live import MarketFeedDisconnected
from app.markets.reducer import RawMarketEvent


class ReplayMarketFeed:
    def __init__(
        self,
        fixture_path: Path | str,
        *,
        speed: float = 1000.0,
        now_fn: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], object] | None = None,
    ) -> None:
        self._path = Path(fixture_path)
        self._speed = speed
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._sleep = sleep_fn or asyncio.sleep

    def stream_market(
        self, market_id: str, asset_ids: tuple[str, ...]
    ) -> AsyncIterator[RawMarketEvent]:
        feed = self

        async def generator() -> AsyncIterator[RawMarketEvent]:
            last_offset = 0
            for line in feed._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                offset = int(record.get("t_offset_ms", 0))
                delay = (offset - last_offset) / 1000 / feed._speed
                if delay > 0:
                    await feed._sleep(delay)
                last_offset = offset
                event_type = str(record.get("event_type", ""))
                if event_type == "disconnect":
                    raise MarketFeedDisconnected("replay_disconnect")
                yield RawMarketEvent(
                    event_type=event_type,
                    asset_id=str(record.get("asset_id", "")),
                    payload=dict(record.get("payload", {})),
                    received_at=feed._now(),
                )

        return generator()

    def subscribe(self, asset_ids: tuple[str, ...]) -> AsyncIterator[RawMarketEvent]:
        return self.stream_market("", asset_ids)
