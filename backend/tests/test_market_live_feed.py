"""Public Polymarket market WebSocket feed tests (T60).

The feed must subscribe only to the public market channel, send keep-alive
pings on the official interval, translate wire messages into typed raw
events, ignore PONG/last-trade noise and surface disconnects without
leaking URLs or identifiers.
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.markets.live import MarketFeedDisconnected, PolymarketMarketFeed

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TOKEN_A = "990001112223334445551"


class FakeWebSocketConnection:
    """Scripted connection: queued inbound frames, recorded outbound sends."""

    def __init__(self, frames: list, *, close_after: bool = False) -> None:
        self._frames = list(frames)
        self._close_after = close_after
        self.sent: list[str] = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True
        return False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        if self._close_after:
            import websockets.exceptions

            raise websockets.exceptions.ConnectionClosed(None, None)
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def book_frame(asset_id: str = TOKEN_A) -> str:
    return json.dumps(
        {
            "event_type": "book",
            "asset_id": asset_id,
            "market": "0xconditionfake",
            "buys": [{"price": "0.50", "size": "300"}],
            "sells": [{"price": "0.57", "size": "150"}],
            "hash": "hash_a1",
            "timestamp": "1789999200000",
        }
    )


def price_change_frame(asset_id: str = TOKEN_A) -> str:
    return json.dumps(
        {
            "event_type": "price_change",
            "asset_id": asset_id,
            "market": "0xconditionfake",
            "changes": [{"price": "0.53", "side": "BUY", "size": "75"}],
            "hash": "hash_a2",
            "timestamp": "1789999300000",
        }
    )


def tick_frame(asset_id: str = TOKEN_A) -> str:
    return json.dumps(
        {
            "event_type": "tick_size_change",
            "asset_id": asset_id,
            "new_tick_size": "0.01",
            "old_tick_size": "0.001",
            "timestamp": "1789999400000",
        }
    )


async def collect(feed: PolymarketMarketFeed, asset_ids: tuple[str, ...], count: int):
    events = []
    async for event in feed.subscribe(asset_ids):
        events.append(event)
        if len(events) >= count:
            break
    return events


async def test_subscribe_frame_targets_public_market_channel_only():
    connection = FakeWebSocketConnection([book_frame(), price_change_frame()])
    urls: list[str] = []

    def factory(url: str):
        urls.append(url)
        return connection

    feed = PolymarketMarketFeed(
        ws_url="wss://ws-subscriptions-clob.polymarket.com/ws/market",
        websocket_factory=factory,
        now_fn=lambda: NOW,
    )
    await collect(feed, (TOKEN_A,), 2)

    assert urls == ["wss://ws-subscriptions-clob.polymarket.com/ws/market"]
    subscribe_frames = [
        json.loads(message) for message in connection.sent if message.startswith("{")
    ]
    assert subscribe_frames[0] == {"type": "market", "assets_ids": [TOKEN_A]}
    for frame in subscribe_frames:
        assert frame.get("type") != "user"


async def test_wire_messages_translate_to_typed_raw_events():
    connection = FakeWebSocketConnection(
        [book_frame(), price_change_frame(), tick_frame()]
    )
    feed = PolymarketMarketFeed(
        ws_url="wss://example.invalid/ws/market",
        websocket_factory=lambda url: connection,
        now_fn=lambda: NOW,
    )

    events = await collect(feed, (TOKEN_A,), 3)

    assert [event.event_type for event in events] == [
        "book",
        "price_change",
        "tick_size_change",
    ]
    assert all(event.asset_id == TOKEN_A for event in events)
    assert events[0].payload["hash"] == "hash_a1"
    assert all(event.received_at == NOW for event in events)


async def test_pong_and_unknown_noise_frames_are_ignored():
    connection = FakeWebSocketConnection(
        [
            "PONG",
            "not-json",
            json.dumps({"event_type": "last_trade_price", "asset_id": TOKEN_A}),
            book_frame(),
        ]
    )
    feed = PolymarketMarketFeed(
        ws_url="wss://example.invalid/ws/market",
        websocket_factory=lambda url: connection,
        now_fn=lambda: NOW,
    )

    events = await collect(feed, (TOKEN_A,), 1)

    assert len(events) == 1
    assert events[0].event_type == "book"


async def test_ping_is_sent_on_the_configured_interval():
    frames = [book_frame()]
    connection = FakeWebSocketConnection(frames)
    clock = {"t": 0.0}

    async def fake_sleep(seconds: float) -> None:
        clock["t"] += seconds
        # Always yield so the keep-alive loop cannot starve the consumer.
        await asyncio.sleep(0)

    feed = PolymarketMarketFeed(
        ws_url="wss://example.invalid/ws/market",
        websocket_factory=lambda url: connection,
        ping_interval_seconds=10.0,
        now_fn=lambda: NOW,
        sleep_fn=fake_sleep,
    )

    async def run() -> None:
        count = 0
        async for _ in feed.subscribe((TOKEN_A,)):
            count += 1
            if count >= 1:
                # Let the keep-alive loop run a few virtual intervals.
                for _ in range(3):
                    await asyncio.sleep(0)
                return

    await asyncio.wait_for(run(), timeout=5)
    await feed.shutdown()
    assert connection.sent.count("PING") >= 1


async def test_disconnect_surfaces_typed_signal_without_leakage():
    connection = FakeWebSocketConnection([book_frame()], close_after=True)
    feed = PolymarketMarketFeed(
        ws_url="wss://example.invalid/ws/market?secret=nothing",
        websocket_factory=lambda url: connection,
        now_fn=lambda: NOW,
    )

    events = []
    with pytest.raises(MarketFeedDisconnected) as error:
        async for event in feed.subscribe((TOKEN_A,)):
            events.append(event)

    assert len(events) == 1
    message = str(error.value)
    assert "wss://" not in message
    assert "example.invalid" not in message
