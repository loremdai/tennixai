"""Broad, read-only Polymarket quote feed (T91)."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.markets.models import MarketExternalId, MarketStatus
from app.markets.quotes import QuoteSnapshotRecord, QuoteSource, QuoteState
from app.persistence.market_repositories import MarketOverviewRow
from app.runtime.market_catalog_quote_feed import (
    CATALOG_QUOTE_SOURCE,
    MarketCatalogQuoteFeed,
    TokenOutcomeRef,
    decode_best_bid_ask,
)

NOW = datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
TOKEN_A = "opaque-token-a"
TOKEN_B = "opaque-token-b"
TOKEN_C = "opaque-token-c"


def frame(event_type="best_bid_ask", asset_id=TOKEN_A, **values):
    return json.dumps({"event_type": event_type, "asset_id": asset_id, **values})


def route(market_id: str, outcome_index: int) -> TokenOutcomeRef:
    return TokenOutcomeRef(market_id=market_id, outcome_index=outcome_index)


def row(
    market_id: str,
    *,
    status: str = MarketStatus.OPEN.value,
    player_ids=(None, None),
) -> MarketOverviewRow:
    return MarketOverviewRow(
        market_id=market_id,
        question=f"Supplier question {market_id}",
        status=status,
        rules_version=1,
        observed_at=NOW,
        event_start=NOW + timedelta(hours=1),
        updated_at=NOW,
        outcome_a_player_id=player_ids[0],
        outcome_a_name="Supplier A",
        outcome_b_player_id=player_ids[1],
        outcome_b_name="Supplier B",
        active_match_id=None,
        link_evidence_available=False,
    )


class FakeMarkets:
    def __init__(self, rows, token_pairs):
        self.rows = rows
        self.token_pairs = token_pairs

    async def list_market_overviews(self):
        return list(self.rows)

    async def list_external_ids(self, market_ids):
        return {
            market_id: MarketExternalId(
                market_id=market_id,
                provider="polymarket",
                provider_event_id=f"event_{market_id}",
                condition_id=f"condition_{market_id}",
                token_ids=self.token_pairs[market_id],
            )
            for market_id in market_ids
            if market_id in self.token_pairs
        }


class FakeProjections:
    def __init__(self):
        self.writes: list[QuoteSnapshotRecord] = []

    async def upsert(self, record):
        self.writes.append(record)
        return True


class FakeHealth:
    def __init__(self):
        self.successes = []
        self.failures = []
        self.success_event = asyncio.Event()
        self.failure_event = asyncio.Event()

    async def mark_success(self, source, *, tracked=0):
        self.successes.append((source, tracked))
        self.success_event.set()

    async def mark_degraded(self, source, reason_code):
        self.failures.append((source, reason_code))
        self.failure_event.set()


class FakeSocket:
    def __init__(self, *, disconnect=False, auto_pong=False):
        self.sent: list[str] = []
        self.closed = False
        self.disconnect = disconnect
        self.auto_pong = auto_pong
        self.pongs: asyncio.Queue[str] = asyncio.Queue()
        self.release = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True
        return False

    async def send(self, message):
        self.sent.append(message)
        if self.auto_pong and message == "PING":
            await self.pongs.put("PONG")

    async def recv(self):
        if self.disconnect:
            raise ConnectionError("wire disconnected")
        if self.auto_pong:
            return await self.pongs.get()
        await self.release.wait()
        await asyncio.sleep(3600)


def make_feed(*, markets=None, projections=None, baseline=None, **kwargs):
    return MarketCatalogQuoteFeed(
        markets=markets or FakeMarkets([], {}),
        projections=projections or FakeProjections(),
        baseline=baseline or _noop_baseline,
        health=kwargs.pop("health", FakeHealth()),
        clock=lambda: NOW,
        **kwargs,
    )


async def _noop_baseline():
    return None


def test_decoder_uses_private_token_route_and_ignores_other_events():
    routes = {TOKEN_A: route("market-internal-1", 0)}

    update = decode_best_bid_ask(
        frame(best_bid="0.57", best_ask="0.59"), routes, received_at=NOW
    )

    assert update is not None
    assert update.market_id == "market-internal-1"
    assert update.outcome_index == 0
    assert update.best_bid == "0.57" and update.best_ask == "0.59"
    assert update.received_at == NOW
    explicit_empty = decode_best_bid_ask(
        frame(best_bid=None, best_ask="1"), routes, received_at=NOW
    )
    assert explicit_empty is not None
    assert explicit_empty.has_best_bid and explicit_empty.best_bid is None
    assert (
        decode_best_bid_ask(
            frame(best_bid="1.01", best_ask="1"), routes, received_at=NOW
        )
        is None
    )
    assert decode_best_bid_ask(frame("price_change"), routes, received_at=NOW) is None
    assert (
        decode_best_bid_ask(
            frame(asset_id="unknown-token", best_bid="0.5"), routes, received_at=NOW
        )
        is None
    )


async def test_feed_loads_idless_listings_and_coalesces_latest_outcome_quotes():
    markets = FakeMarkets(
        [row("market-internal-1"), row("closed", status=MarketStatus.CLOSED.value)],
        {"market-internal-1": (TOKEN_A, TOKEN_B)},
    )
    projections = FakeProjections()
    notifications = []

    async def notify(*, count):
        notifications.append(count)

    feed = make_feed(
        markets=markets,
        projections=projections,
        on_quotes_changed=notify,
    )

    routes = await feed.load_token_routes()
    assert routes == {
        TOKEN_A: route("market-internal-1", 0),
        TOKEN_B: route("market-internal-1", 1),
    }
    assert feed.ingest_frame(frame(asset_id=TOKEN_A, best_bid="0.56"), routes)
    assert feed.ingest_frame(frame(asset_id=TOKEN_A, best_bid="0.57"), routes)
    assert feed.ingest_frame(frame(asset_id=TOKEN_A, best_bid="0.57"), routes)
    assert feed.ingest_frame(
        frame(asset_id=TOKEN_B, best_bid="0.40", best_ask="0.42"), routes
    )

    assert await feed.flush_quotes() == 0  # outcome A still has no live ask
    assert feed.ingest_frame(frame(asset_id=TOKEN_A, best_ask="0.59"), routes)
    assert await feed.flush_quotes() == 1
    assert len(projections.writes) == 1
    record = projections.writes[0]
    assert record.source is QuoteSource.REALTIME
    assert record.state is QuoteState.REALTIME
    assert record.outcome_bids == ("0.57", "0.40")
    assert record.outcome_asks == ("0.59", "0.42")
    assert record.levels is None
    assert record.best_bid is None and record.best_ask is None
    assert TOKEN_A not in record.model_dump_json()
    assert TOKEN_B not in record.model_dump_json()
    assert notifications == [1]


async def test_feed_only_flushes_a_market_after_both_outcomes_have_live_values():
    projections = FakeProjections()
    feed = make_feed(projections=projections)
    routes = {TOKEN_A: route("market-internal-1", 0)}

    assert feed.ingest_frame(
        frame(asset_id=TOKEN_A, best_bid="0.55", best_ask="0.57"), routes
    )
    assert await feed.flush_quotes() == 0
    assert projections.writes == []


async def test_dynamic_subscription_updates_use_documented_operations():
    feed = make_feed()
    socket = FakeSocket()
    previous = {TOKEN_A: route("m1", 0), TOKEN_B: route("m1", 1)}
    current = {TOKEN_B: route("m1", 1), TOKEN_C: route("m2", 0)}

    await feed.update_subscriptions(socket, previous, current)

    frames = [json.loads(message) for message in socket.sent]
    assert frames == [
        {"assets_ids": [TOKEN_A], "operation": "unsubscribe"},
        {"assets_ids": [TOKEN_C], "operation": "subscribe"},
    ]


async def test_reconnect_runs_rest_baseline_and_shutdown_closes_and_awaits_socket():
    baseline_calls = []
    health = FakeHealth()
    first = FakeSocket(disconnect=True)
    second = FakeSocket()
    connections = iter((first, second))
    connected = asyncio.Event()

    async def baseline():
        baseline_calls.append(True)

    def connector(_url):
        connection = next(connections)
        if connection is second:
            connected.set()
        return connection

    async def immediate_sleep(_seconds):
        await asyncio.sleep(0)

    feed = make_feed(
        markets=FakeMarkets(
            [row("market-internal-1")],
            {"market-internal-1": (TOKEN_A, TOKEN_B)},
        ),
        baseline=baseline,
        websocket_factory=connector,
        health=health,
        ping_interval_seconds=3600,
        sleep_fn=immediate_sleep,
        reconnect_delay_seconds=0,
    )
    task = asyncio.create_task(feed.run())
    try:
        await asyncio.wait_for(connected.wait(), timeout=2)
        assert len(baseline_calls) == 2
        assert health.failures == [(CATALOG_QUOTE_SOURCE, "CONNECTION_ERROR")]
        assert health.successes[-1][0] == CATALOG_QUOTE_SOURCE
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert second.closed
    assert json.loads(second.sent[0]) == {
        "assets_ids": [TOKEN_A, TOKEN_B],
        "type": "market",
        "custom_feature_enabled": True,
    }


async def test_idle_feed_uses_pong_as_liveness_not_price_events():
    socket = FakeSocket(auto_pong=True)
    health = FakeHealth()
    projections = FakeProjections()
    feed = make_feed(
        markets=FakeMarkets(
            [row("market-internal-1")],
            {"market-internal-1": (TOKEN_A, TOKEN_B)},
        ),
        projections=projections,
        health=health,
        websocket_factory=lambda _url: socket,
        ping_interval_seconds=0.01,
        catalog_refresh_seconds=3600,
        flush_interval_seconds=3600,
    )
    task = asyncio.create_task(feed.run())
    try:
        await asyncio.wait_for(health.success_event.wait(), timeout=2)
        health.success_event.clear()
        await asyncio.wait_for(health.success_event.wait(), timeout=2)
        assert health.successes[-1][0] == CATALOG_QUOTE_SOURCE
        assert projections.writes == []
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert socket.closed


async def test_missing_pong_degrades_feed_and_reconnects():
    socket = FakeSocket()
    health = FakeHealth()
    feed = make_feed(
        markets=FakeMarkets(
            [row("market-internal-1")],
            {"market-internal-1": (TOKEN_A, TOKEN_B)},
        ),
        health=health,
        websocket_factory=lambda _url: socket,
        ping_interval_seconds=0.01,
        catalog_refresh_seconds=3600,
        flush_interval_seconds=3600,
        reconnect_delay_seconds=3600,
    )
    task = asyncio.create_task(feed.run())
    try:
        await asyncio.wait_for(health.failure_event.wait(), timeout=2)
        assert health.failures == [(CATALOG_QUOTE_SOURCE, "HEARTBEAT_TIMEOUT")]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert socket.closed
