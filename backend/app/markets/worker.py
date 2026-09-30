"""Market realtime worker (T60).

Bounded per-market queues, dynamic subscribe/unsubscribe from durable
tracking demand, REST-first baselines, REST reconcile after any disconnect
or overflow, Redis hot-state loss recovery, batched observation persistence
and scheduled 14-day raw cleanup. High-frequency book deltas never write SQL
synchronously; only decision-relevant observations are batched, and the
paper ledger is never touched from this loop.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.errors import AppError
from app.markets.live import MarketFeedClosed, MarketFeedDisconnected
from app.markets.publisher import MarketHotPublisher
from app.markets.reducer import MarketBookReducer, RawMarketEvent

RAW_RETENTION_DAYS = 14


@dataclass
class _MarketSubscription:
    market_id: str
    tokens: tuple[str, str]
    reducer: MarketBookReducer
    queue: asyncio.Queue
    stream: Any
    state: str = "live"  # live | reconnecting | closed
    reader: asyncio.Task | None = None
    started_at: datetime | None = None
    last_event_at: datetime | None = None
    dropped: int = 0
    needs_reconcile: bool = False


@dataclass
class _WorkerDeps:
    feed: Any
    rest: Any
    publisher: MarketHotPublisher
    observations: Any
    raw: Any


class MarketWorker:
    def __init__(
        self,
        *,
        feed,
        rest,
        publisher: MarketHotPublisher,
        observations,
        raw,
        demand_source: Callable[[], Awaitable[set[str]]],
        token_lookup: Callable[[str], Awaitable[tuple[str, str]]],
        now: Callable[[], datetime],
        max_subscriptions: int = 8,
        queue_size: int = 64,
        batch_size: int = 8,
        retention_days: int = RAW_RETENTION_DAYS,
        cleanup_interval_cycles: int = 50,
        on_state: Callable[[str, Any], Awaitable[None]] | None = None,
        on_connection: Callable[[str, str], Awaitable[None]] | None = None,
        on_resolution_hint: Callable[[str], None] | None = None,
        metrics: Any = None,
        reconcile_timeout_seconds: float = 30,
        reconcile_cycle_seconds: float = 30,
    ) -> None:
        self._deps = _WorkerDeps(feed, rest, publisher, observations, raw)
        self._demand_source = demand_source
        self._token_lookup = token_lookup
        self._now = now
        self._max = max_subscriptions
        self._queue_size = queue_size
        self._batch_size = batch_size
        self._retention_days = retention_days
        self._cleanup_interval = cleanup_interval_cycles
        self._on_state = on_state
        self._on_connection = on_connection
        self._on_resolution_hint = on_resolution_hint
        self._metrics = metrics
        self._reconcile_timeout = reconcile_timeout_seconds
        self._cycle_seconds = reconcile_cycle_seconds
        self._start_cursor: str | None = None
        self._repair_cursor: str | None = None
        self.reconciliation_failures: dict[str, str] = {}
        self._retry: dict[str, tuple[int, datetime]] = {}
        self._retired: set[str] = set()
        # Public so the runtime daemon can aggregate hook failures into one
        # health surface; only counts, never identifiers.
        self.callback_failures: dict[str, int] = {
            "on_state": 0,
            "on_connection": 0,
            "on_resolution_hint": 0,
        }
        self._subs: dict[str, _MarketSubscription] = {}
        self._starting: set[str] = set()
        self._capacity_blocked: set[str] = set()
        self._observation_buffer: list[dict] = []
        self._cycles = 0
        self._stopping = False

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def subscription_state(self, market_id: str) -> str:
        sub = self._subs.get(market_id)
        if sub is not None:
            return sub.state
        if market_id in self._capacity_blocked:
            return "capacity_limited"
        return "closed"

    def dropped_events(self, market_id: str) -> int:
        sub = self._subs.get(market_id)
        return sub.dropped if sub is not None else 0

    def active_market_ids(self) -> tuple[str, ...]:
        """Sorted copy of the currently subscribed market IDs; safe to call
        from any owner at any time without touching worker internals."""
        return tuple(sorted(key for key, sub in self._subs.items() if sub.state != "closed"))

    async def reconcile_demand_once(self) -> None:
        # Let reader tasks surface queued frames/disconnects before pumping.
        await asyncio.sleep(0)
        self._cycles += 1
        demand = await self._demand_source()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._cycle_seconds
        self._retired.intersection_update(demand)
        self._capacity_blocked.intersection_update(demand)
        for market_id in set(self._retry) - demand:
            self._retry.pop(market_id, None)
            self.reconciliation_failures.pop(market_id, None)

        for market_id in list(self._subs):
            if market_id not in demand:
                await self._close(market_id)

        active = sum(1 for sub in self._subs.values() if sub.state != "closed")
        for market_id in self._rotated(demand, self._start_cursor):
            if market_id in self._retired or not self._retry_due(market_id):
                continue
            if market_id in self._subs:
                self._capacity_blocked.discard(market_id)
                continue
            if active >= self._max:
                self._capacity_blocked.add(market_id)
                continue
            self._capacity_blocked.discard(market_id)
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            self._start_cursor = market_id
            if await self._recover_market(market_id, self._start(market_id), timeout=remaining):
                active += 1

        for market_id in self._rotated(self._subs, self._repair_cursor):
            sub = self._subs.get(market_id)
            if sub is None:
                continue
            if sub.state == "closed":
                # A normally closed subscription has no stream to reconcile
                # and must not be restarted while it is still in demand.
                continue
            if self._retry_due(sub.market_id):
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                self._repair_cursor = market_id
                await self._recover_market(sub.market_id, self._reconcile_subscription(sub), timeout=remaining)

        await self._flush_observations()

        if self._cycles % self._cleanup_interval == 0:
            await self._deps.raw.purge_raw_events(
                self._now() - timedelta(days=self._retention_days)
            )

    async def run_forever(self, interval_seconds: float = 0.1) -> None:
        self._stopping = False
        while not self._stopping:
            await self.reconcile_demand_once()
            await asyncio.sleep(interval_seconds)

    async def stop(self) -> None:
        self._stopping = True
        for market_id in list(self._subs):
            await self._close(market_id)
        # Graceful shutdown preserves buffered observations through the same
        # bounded batch path a reconcile cycle uses; nothing is deleted.
        await self._flush_observations()

    async def run_replay_once(self, feed) -> None:
        """Consume a deterministic replay feed to completion (replay gates)."""
        demand = await self._demand_source()
        for market_id in sorted(demand):
            if market_id not in self._subs:
                await self._start(market_id)
            sub = self._subs[market_id]
            stream = feed.stream_market(market_id, sub.tokens)
            try:
                async for event in stream:
                    await self._apply(sub, event)
            except MarketFeedDisconnected:
                await self._rest_reconcile(
                    sub, reason="replay_disconnect", record_gap=True
                )
        await self._flush_observations()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _retry_due(self, market_id: str) -> bool:
        retry = self._retry.get(market_id)
        return retry is None or self._now() >= retry[1]

    @staticmethod
    def _rotated(markets, cursor: str | None) -> list[str]:
        ordered = sorted(markets)
        if cursor is None:
            return ordered
        return [key for key in ordered if key > cursor] + [key for key in ordered if key <= cursor]

    async def _reconcile_subscription(self, sub: _MarketSubscription) -> None:
        if sub.state == "reconnecting":
            await self._rest_reconcile(sub, reason="reconnect", record_gap=True)
        elif sub.needs_reconcile:
            await self._rest_reconcile(sub, reason="queue_overflow", record_gap=True)
        elif await self._deps.publisher.get_hot_book(sub.market_id) is None:
            await self._rest_reconcile(sub, reason="hot_state_lost", record_gap=False)
        await self._pump(sub)

    async def _recover_market(self, market_id: str, operation, *, timeout: float | None = None) -> bool:
        try:
            async with asyncio.timeout(min(self._reconcile_timeout, timeout if timeout is not None else self._reconcile_timeout)):
                await operation
        except Exception as exc:
            if isinstance(exc, AppError) and exc.code == "market_closed":
                await self._retire(market_id)
                return False
            code = "UPSTREAM_TIMEOUT" if isinstance(exc, TimeoutError) else "MARKET_RECOVERY_FAILED"
            if isinstance(exc, AppError) and exc.code.isidentifier():
                code = exc.code.upper()
            self.reconciliation_failures[market_id] = code
            attempt = self._retry.get(market_id, (0, self._now()))[0] + 1
            self._retry[market_id] = (attempt, self._now() + timedelta(seconds=min(60, 5 * 2 ** min(attempt - 1, 4))))
            sub = self._subs.get(market_id)
            if sub is not None:
                sub.state = "reconnecting"
            await self._deps.publisher.publish_gap(market_id, code)
            await self._notify_connection(market_id, "reconnecting")
            return False
        self.reconciliation_failures.pop(market_id, None)
        self._retry.pop(market_id, None)
        return True

    async def _retire(self, market_id: str) -> None:
        if market_id in self._retired:
            return
        self._retired.add(market_id)
        self.reconciliation_failures.pop(market_id, None)
        self._retry.pop(market_id, None)
        await self._close(market_id)
        await self._deps.publisher.publish_gap(market_id, "MARKET_CLOSED")
        await self._notify_connection(market_id, "closed")
        if self._on_resolution_hint is not None:
            try:
                self._on_resolution_hint(market_id)
            except Exception:
                self.callback_failures["on_resolution_hint"] += 1

    async def _start(self, market_id: str) -> None:
        # Re-entrancy guard: the runtime daemon is the single sequential
        # caller, but a duplicated concurrent start must never double
        # subscribe or double publish a baseline.
        if market_id in self._starting or market_id in self._subs:
            return
        self._starting.add(market_id)
        try:
            tokens = await self._token_lookup(market_id)
            rest_state = await self._deps.rest.get_order_book(market_id)
            player_tokens = {
                book.outcome_player_id: token
                for book, token in zip(rest_state.books, tokens, strict=True)
            }
            reducer = MarketBookReducer(
                market_id=market_id,
                token_players={
                    token: player for player, token in player_tokens.items()
                },
                now_fn=self._now,
            )
            reducer.baseline_from_rest(rest_state, player_tokens)
            await self._deps.publisher.publish_book(market_id, rest_state)
            await self._notify_state(market_id, rest_state)
            sub = _MarketSubscription(
                market_id=market_id,
                tokens=tokens,
                reducer=reducer,
                queue=asyncio.Queue(maxsize=self._queue_size),
                stream=self._deps.feed.stream_market(market_id, tokens),
                started_at=self._now(),
            )
            self._subs[market_id] = sub
            sub.reader = asyncio.create_task(self._read(sub))
        finally:
            self._starting.discard(market_id)

    async def _read(self, sub: _MarketSubscription) -> None:
        """Receive callback does no I/O: validate-and-enqueue only. A full
        bounded queue drops the event and marks the sub for reconcile."""
        try:
            async for event in sub.stream:
                sub.last_event_at = event.received_at
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    sub.dropped += 1
                    sub.needs_reconcile = True
                    if self._metrics is not None:
                        self._metrics.increment("queue_overflow")
        except asyncio.CancelledError:
            raise
        except MarketFeedClosed:
            # Provider-side normal end (a finished market): stop this stream
            # without a gap and without marking the source failed. The entry
            # stays parked until the demand source drops it.
            sub.state = "closed"
            await self._notify_connection(sub.market_id, "closed")
        except MarketFeedDisconnected:
            sub.state = "reconnecting"
        except Exception:
            # Any transport failure is a disconnect; reconnecting is this
            # worker's job and diagnostics never carry connection URIs.
            sub.state = "reconnecting"

    async def _close(self, market_id: str) -> None:
        sub = self._subs.pop(market_id, None)
        if sub is None:
            return
        sub.state = "closed"
        if sub.reader is not None and not sub.reader.done():
            sub.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sub.reader
        sub.reader = None

    async def _rest_reconcile(
        self, sub: _MarketSubscription, *, reason: str, record_gap: bool
    ) -> None:
        # A recorded gap is a real upstream interruption: report the stable
        # "reconnecting" transition before rebuilding from REST, and "live"
        # once the reconcile succeeded. Silent hot-state recovery is not a
        # connection transition and reports nothing.
        if record_gap:
            await self._notify_connection(sub.market_id, "reconnecting")
        rest_state = await self._deps.rest.get_order_book(sub.market_id)
        player_tokens = {
            book.outcome_player_id: token
            for book, token in zip(rest_state.books, sub.tokens, strict=True)
        }
        sub.reducer.baseline_from_rest(rest_state, player_tokens)
        await self._deps.publisher.publish_book(sub.market_id, rest_state)
        await self._notify_state(sub.market_id, rest_state)
        if self._metrics is not None:
            self._metrics.increment("reconnects")
        if record_gap:
            started = sub.last_event_at or sub.started_at or self._now()
            ended = self._now()
            await self._deps.observations.record_tracking_gap(
                market_id=sub.market_id,
                match_id=None,
                reason=reason,
                started_at=started,
                ended_at=ended,
            )
            await self._deps.publisher.publish_gap(sub.market_id, reason)
            if self._metrics is not None:
                self._metrics.increment("tracking_gaps")
        # Drain anything queued from the dead stream, then restart.
        while not sub.queue.empty():
            sub.queue.get_nowait()
        sub.needs_reconcile = False
        sub.dropped = 0
        if sub.state != "closed":
            sub.stream = self._deps.feed.stream_market(sub.market_id, sub.tokens)
            if sub.reader is not None and not sub.reader.done():
                sub.reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sub.reader
            sub.reader = asyncio.create_task(self._read(sub))
            sub.state = "live"
            if record_gap:
                await self._notify_connection(sub.market_id, "live")

    async def _pump(self, sub: _MarketSubscription) -> None:
        while True:
            try:
                event: RawMarketEvent = sub.queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            await self._apply(sub, event)

    async def _notify_state(self, market_id: str, state: Any) -> None:
        """Downstream decision orchestration (P3); a failure there must never
        corrupt market hot state or suppress the just-published book."""
        if self._on_state is None:
            return
        try:
            await self._on_state(market_id, state)
        except Exception:
            self.callback_failures["on_state"] += 1
            if self._metrics is not None:
                self._metrics.increment("decision_suppressed")

    async def _notify_connection(self, market_id: str, state: str) -> None:
        """Report stable connection transitions downstream; only the market
        ID and the canonical state string ever leave the worker."""
        if self._on_connection is None:
            return
        try:
            await self._on_connection(market_id, state)
        except Exception:
            self.callback_failures["on_connection"] += 1

    async def _apply(self, sub: _MarketSubscription, event: RawMarketEvent) -> None:
        reduction = sub.reducer.apply_event(event)
        if reduction.needs_snapshot:
            await self._rest_reconcile(sub, reason="missing_baseline", record_gap=True)
            return
        if reduction.changed:
            state = sub.reducer.current_state()
            if state is not None:
                await self._deps.publisher.publish_book(sub.market_id, state)
                await self._notify_state(sub.market_id, state)
                self._observation_buffer.append(
                    {
                        "market_id": sub.market_id,
                        "match_id": None,
                        "kind": "book_change",
                        "payload": {
                            "sequence": state.sequence,
                            "book_hash": state.book_hash,
                        },
                        "observed_at": event.received_at.isoformat(),
                    }
                )
        if reduction.resolution_requested:
            await self._retire(sub.market_id)
            self._observation_buffer.append(
                {
                    "market_id": sub.market_id,
                    "match_id": None,
                    "kind": "resolution_event",
                    "payload": {"asset_event": True},
                    "observed_at": event.received_at.isoformat(),
                }
            )

    async def _flush_observations(self) -> None:
        while self._observation_buffer:
            batch = self._observation_buffer[: self._batch_size]
            self._observation_buffer = self._observation_buffer[self._batch_size :]
            await self._deps.observations.save_observations(batch)
