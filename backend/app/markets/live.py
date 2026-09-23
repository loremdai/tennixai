"""Public Polymarket market WebSocket feed (T60).

Subscribes only to the public market channel — never the user/authenticated
channel — sends keep-alive pings on the official interval, translates wire
messages into typed raw events and surfaces disconnects without leaking
URLs, tokens or any credential (none exist for this read-only feed).
"""

import asyncio
import contextlib
import json
from functools import partial
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import websockets
import websockets.exceptions

from app.markets.reducer import RawMarketEvent

DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_PING_INTERVAL_SECONDS = 10.0
CONSUMED_EVENT_TYPES = frozenset(
    {"book", "price_change", "tick_size_change", "resolution"}
)


class MarketFeedDisconnected(Exception):
    """Transport-level disconnect; the reason never contains URIs or IDs."""


class MarketFeedClosed(Exception):
    """The provider closed this subscription normally (a finished market).

    Not a fault: the worker stops that subscription without recording a gap
    and without marking the whole market source as failed.
    """


class PolymarketMarketFeed:
    def __init__(
        self,
        *,
        ws_url: str = DEFAULT_WS_URL,
        websocket_factory: Callable[[str], object] | None = None,
        ping_interval_seconds: float = DEFAULT_PING_INTERVAL_SECONDS,
        now_fn: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], object] | None = None,
    ) -> None:
        self._ws_url = ws_url
        self._connect = websocket_factory or partial(websockets.connect, proxy=None)
        self._ping_interval = ping_interval_seconds
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._sleep = sleep_fn or asyncio.sleep
        self._ping_tasks: set[asyncio.Task] = set()

    async def shutdown(self) -> None:
        """Cancel every in-flight keepalive task for this feed instance."""
        tasks = [task for task in self._ping_tasks if not task.done()]
        self._ping_tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    def subscribe(self, asset_ids: tuple[str, ...]) -> AsyncIterator[RawMarketEvent]:
        feed = self

        async def generator() -> AsyncIterator[RawMarketEvent]:
            async with feed._connect(feed._ws_url) as connection:  # type: ignore[operator]
                subscribe_frame = json.dumps(
                    {"type": "market", "assets_ids": list(asset_ids)}
                )
                await connection.send(subscribe_frame)

                async def keep_alive() -> None:
                    # One task per connection: a second subscription must
                    # never clobber the first one's keepalive.
                    while True:
                        await feed._sleep(feed._ping_interval)
                        try:
                            await connection.send("PING")
                        except Exception:
                            # A dead socket ends this subscription through the
                            # normal receive path instead of a silent task.
                            with contextlib.suppress(Exception):
                                await connection.close()
                            return

                ping_task = asyncio.create_task(keep_alive())
                feed._ping_tasks.add(ping_task)
                try:
                    while True:
                        try:
                            raw = await connection.recv()
                        except websockets.exceptions.ConnectionClosedOK as error:
                            # A finished market closes normally: an explicit
                            # lifecycle branch, not a transport failure.
                            raise MarketFeedClosed("normal_close") from error
                        except websockets.exceptions.ConnectionClosed as error:
                            raise MarketFeedDisconnected("connection_closed") from error
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        if raw in ("PONG", "PING"):
                            continue
                        try:
                            payload = json.loads(raw)
                        except ValueError:
                            continue
                        if not isinstance(payload, dict):
                            continue
                        event_type = str(payload.get("event_type") or "")
                        if event_type not in CONSUMED_EVENT_TYPES:
                            continue
                        yield RawMarketEvent(
                            event_type=event_type,
                            asset_id=str(payload.get("asset_id") or ""),
                            payload=payload,
                            received_at=feed._now(),
                        )
                finally:
                    feed._ping_tasks.discard(ping_task)
                    if not ping_task.done():
                        ping_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await ping_task

        return generator()

    def stream_market(
        self, market_id: str, asset_ids: tuple[str, ...]
    ) -> AsyncIterator[RawMarketEvent]:
        return self.subscribe(asset_ids)
