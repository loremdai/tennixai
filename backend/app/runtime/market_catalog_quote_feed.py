"""Read-only, broad Polymarket quote stream for the display catalog."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Any

import websockets

from app.markets.models import MarketStatus
from app.markets.quotes import realtime_listing_quote_record
from app.runtime.health import stable_reason_code

CATALOG_QUOTE_SOURCE = "polymarket_catalog_quotes"
DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


@dataclass(frozen=True)
class TokenOutcomeRef:
    market_id: str
    outcome_index: int


@dataclass(frozen=True)
class BestBidAskUpdate:
    market_id: str
    outcome_index: int
    best_bid: str | None
    best_ask: str | None
    has_best_bid: bool
    has_best_ask: bool
    received_at: datetime


@dataclass
class _TokenQuote:
    best_bid: str | None = None
    best_ask: str | None = None
    best_bid_at: datetime | None = None
    best_ask_at: datetime | None = None

    @property
    def ready(self) -> bool:
        return self.best_bid_at is not None and self.best_ask_at is not None


@dataclass
class _MarketQuote:
    outcomes: list[_TokenQuote] = field(
        default_factory=lambda: [_TokenQuote(), _TokenQuote()]
    )


class _BaselineFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _HeartbeatTimeout(Exception):
    code = "HEARTBEAT_TIMEOUT"


def _decode_price(value: Any) -> tuple[bool, str | None]:
    if value is None:
        return True, None
    if not isinstance(value, str):
        return False, None
    try:
        price = Decimal(value)
    except InvalidOperation:
        return False, None
    if not price.is_finite() or not Decimal("0") <= price <= Decimal("1"):
        return False, None
    return True, value


def decode_best_bid_ask(
    raw: str | bytes,
    token_routes: Mapping[str, TokenOutcomeRef],
    *,
    received_at: datetime,
) -> BestBidAskUpdate | None:
    """Decode only Polymarket's documented best_bid_ask event shape."""
    try:
        payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("event_type") != "best_bid_ask":
        return None
    token_id = payload.get("asset_id")
    route = token_routes.get(token_id) if isinstance(token_id, str) else None
    if route is None or route.outcome_index not in (0, 1):
        return None
    has_bid = "best_bid" in payload
    has_ask = "best_ask" in payload
    if not has_bid and not has_ask:
        return None
    valid_bid, best_bid = (
        _decode_price(payload.get("best_bid")) if has_bid else (True, None)
    )
    valid_ask, best_ask = (
        _decode_price(payload.get("best_ask")) if has_ask else (True, None)
    )
    if not valid_bid or not valid_ask:
        return None
    return BestBidAskUpdate(
        market_id=route.market_id,
        outcome_index=route.outcome_index,
        best_bid=best_bid,
        best_ask=best_ask,
        has_best_bid=has_bid,
        has_best_ask=has_ask,
        received_at=received_at,
    )


class MarketCatalogQuoteFeed:
    """One reconnecting WebSocket that mirrors all active listing quotes.

    Its bounded state is one latest-value pair per open/scheduled market; it
    never enters the strict decision worker or the Paper service.
    """

    def __init__(
        self,
        *,
        markets: Any,
        projections: Any,
        baseline: Callable[[], Any],
        health: Any,
        clock: Callable[[], datetime],
        ws_url: str = DEFAULT_WS_URL,
        websocket_factory: Callable[[str], Any] | None = None,
        ping_interval_seconds: float = 10,
        catalog_refresh_seconds: float = 30,
        flush_interval_seconds: float = 0.25,
        reconnect_delay_seconds: float = 5,
        max_reconnect_delay_seconds: float = 60,
        fresh_seconds: int = 300,
        on_quotes_changed: Callable[..., Any] | None = None,
        sleep_fn: Callable[[float], Any] | None = None,
    ) -> None:
        self._markets = markets
        self._projections = projections
        self._baseline = baseline
        self._health = health
        self._clock = clock
        self._ws_url = ws_url
        self._connect = websocket_factory or partial(
            websockets.connect, proxy=None, ping_interval=None
        )
        self._ping_interval = ping_interval_seconds
        self._catalog_refresh = catalog_refresh_seconds
        self._flush_interval = flush_interval_seconds
        self._reconnect_delay = reconnect_delay_seconds
        self._max_reconnect_delay = max_reconnect_delay_seconds
        self._fresh_seconds = fresh_seconds
        self._on_quotes_changed = on_quotes_changed
        self._sleep = sleep_fn or asyncio.sleep
        self._send_lock = asyncio.Lock()
        self._quotes: dict[str, _MarketQuote] = {}
        self._dirty: set[str] = set()
        self._connection_healthy: bool | None = None

    async def load_token_routes(self) -> dict[str, TokenOutcomeRef]:
        rows = await self._markets.list_market_overviews()
        eligible = [
            row
            for row in rows
            if row.status in {MarketStatus.OPEN.value, MarketStatus.SCHEDULED.value}
        ]
        externals = await self._markets.list_external_ids(
            [row.market_id for row in eligible]
        )
        routes: dict[str, TokenOutcomeRef] = {}
        ambiguous: set[str] = set()
        for row in eligible:
            external = externals.get(row.market_id)
            if external is None or len(external.token_ids) != 2:
                continue
            for index, token_id in enumerate(external.token_ids):
                if not token_id or token_id in ambiguous:
                    continue
                route = TokenOutcomeRef(row.market_id, index)
                existing = routes.get(token_id)
                if existing is not None and existing != route:
                    routes.pop(token_id, None)
                    ambiguous.add(token_id)
                else:
                    routes[token_id] = route
        return routes

    def ingest_frame(
        self,
        raw: str | bytes,
        routes: Mapping[str, TokenOutcomeRef],
        *,
        received_at: datetime | None = None,
    ) -> bool:
        update = decode_best_bid_ask(
            raw,
            routes,
            received_at=received_at or self._clock(),
        )
        if update is None:
            return False
        quote = self._quotes.setdefault(update.market_id, _MarketQuote())
        outcome = quote.outcomes[update.outcome_index]
        if update.has_best_bid:
            outcome.best_bid = update.best_bid
            outcome.best_bid_at = update.received_at
        if update.has_best_ask:
            outcome.best_ask = update.best_ask
            outcome.best_ask_at = update.received_at
        self._dirty.add(update.market_id)
        return True

    async def flush_quotes(self) -> int:
        written = 0
        for market_id in sorted(self._dirty):
            quote = self._quotes.get(market_id)
            if quote is None or not all(outcome.ready for outcome in quote.outcomes):
                continue
            self._dirty.discard(market_id)
            bids = (quote.outcomes[0].best_bid, quote.outcomes[1].best_bid)
            asks = (quote.outcomes[0].best_ask, quote.outcomes[1].best_ask)
            stamps = [
                stamp
                for outcome in quote.outcomes
                for stamp in (outcome.best_bid_at, outcome.best_ask_at)
                if stamp is not None
            ]
            record = realtime_listing_quote_record(
                market_id=market_id,
                outcome_bids=bids,
                outcome_asks=asks,
                as_of=min(stamps),
                fresh_seconds=self._fresh_seconds,
            )
            if await self._projections.upsert(record):
                written += 1
        if written and self._on_quotes_changed is not None:
            await self._on_quotes_changed(count=written)
        return written

    async def update_subscriptions(
        self,
        connection: Any,
        previous: Mapping[str, TokenOutcomeRef],
        current: Mapping[str, TokenOutcomeRef],
    ) -> None:
        removed = sorted(
            token_id
            for token_id, route in previous.items()
            if current.get(token_id) != route
        )
        added = sorted(
            token_id
            for token_id, route in current.items()
            if previous.get(token_id) != route
        )
        affected = {previous[token_id].market_id for token_id in removed} | {
            current[token_id].market_id for token_id in added
        }
        for market_id in affected:
            self._quotes.pop(market_id, None)
            self._dirty.discard(market_id)
        if removed:
            await self._send(
                connection,
                {"assets_ids": removed, "operation": "unsubscribe"},
            )
        if added:
            await self._send(
                connection,
                {"assets_ids": added, "operation": "subscribe"},
            )

    async def run(self) -> None:
        delay = self._reconnect_delay
        while True:
            try:
                routes = await self.load_token_routes()
                if not routes:
                    await self._health.mark_success(CATALOG_QUOTE_SOURCE, tracked=0)
                    await self._mark_connection_state(True)
                    await self._sleep(self._catalog_refresh)
                    continue
                # REST makes startup and every reconnect a calibrated handoff.
                coverage = await self._baseline()
                if coverage is not None:
                    self._health.set_market_coverage(coverage)
                    if coverage.batch_failures:
                        raise _BaselineFailed("MARKET_SNAPSHOT_BATCH_FAILED")
                    if coverage.rate_limited:
                        raise _BaselineFailed("MARKET_SNAPSHOT_RATE_LIMITED")
                async with self._connect(self._ws_url) as connection:
                    self._quotes.clear()
                    self._dirty.clear()
                    await self._send(
                        connection,
                        {
                            "assets_ids": sorted(routes),
                            "type": "market",
                            "custom_feature_enabled": True,
                        },
                    )
                    await self._health.mark_success(
                        CATALOG_QUOTE_SOURCE,
                        tracked=len({route.market_id for route in routes.values()}),
                    )
                    await self._mark_connection_state(True)
                    await self._serve(connection, routes)
                delay = self._reconnect_delay
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - reconnect with sanitized health
                await self._health.mark_degraded(
                    CATALOG_QUOTE_SOURCE, stable_reason_code(exc)
                )
                await self._mark_connection_state(False)
                await self._sleep(delay)
                delay = min(
                    max(delay * 2, self._reconnect_delay), self._max_reconnect_delay
                )

    async def _serve(self, connection: Any, routes: dict[str, TokenOutcomeRef]) -> None:
        async def keep_alive() -> None:
            while True:
                await asyncio.sleep(self._ping_interval)
                try:
                    async with self._send_lock:
                        await connection.send("PING")
                except Exception:
                    with contextlib.suppress(Exception):
                        await connection.close()
                    return

        ping_task = asyncio.create_task(keep_alive())
        loop = asyncio.get_running_loop()
        next_refresh = loop.time() + self._catalog_refresh
        next_flush = loop.time() + self._flush_interval
        last_pong = loop.time()
        tracked = len({route.market_id for route in routes.values()})
        try:
            while True:
                heartbeat_deadline = last_pong + 3 * self._ping_interval
                timeout = max(
                    0.01,
                    min(next_refresh, next_flush, heartbeat_deadline) - loop.time(),
                )
                try:
                    raw = await asyncio.wait_for(connection.recv(), timeout=timeout)
                except TimeoutError:
                    raw = None
                now = loop.time()
                if raw in ("PONG", b"PONG"):
                    last_pong = now
                    await self._health.mark_success(
                        CATALOG_QUOTE_SOURCE, tracked=tracked
                    )
                elif raw not in (None, "PING", b"PING"):
                    self.ingest_frame(raw, routes)
                if now - last_pong > 3 * self._ping_interval:
                    raise _HeartbeatTimeout
                if now >= next_flush:
                    await self.flush_quotes()
                    next_flush = now + self._flush_interval
                if now >= next_refresh:
                    current = await self.load_token_routes()
                    if current != routes:
                        await self.update_subscriptions(connection, routes, current)
                        routes.clear()
                        routes.update(current)
                        tracked = len({route.market_id for route in routes.values()})
                        await self._health.mark_success(
                            CATALOG_QUOTE_SOURCE,
                            tracked=tracked,
                        )
                    next_refresh = now + self._catalog_refresh
        finally:
            ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await ping_task

    async def _send(self, connection: Any, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await connection.send(json.dumps(payload, separators=(",", ":")))

    async def _mark_connection_state(self, healthy: bool) -> None:
        if self._connection_healthy is healthy:
            return
        self._connection_healthy = healthy
        if self._on_quotes_changed is not None:
            await self._on_quotes_changed(count=0)


__all__ = [
    "CATALOG_QUOTE_SOURCE",
    "BestBidAskUpdate",
    "MarketCatalogQuoteFeed",
    "TokenOutcomeRef",
    "decode_best_bid_ask",
]
