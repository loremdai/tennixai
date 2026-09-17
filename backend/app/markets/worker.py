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

from app.markets.live import MarketFeedDisconnected
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
        metrics: Any = None,
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
        self._metrics = metrics
        self._subs: dict[str, _MarketSubscription] = {}
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
        return tuple(sorted(self._subs))

    async def reconcile_demand_once(self) -> None:
        # Let reader tasks surface queued frames/disconnects before pumping.
        await asyncio.sleep(0)
        self._cycles += 1
        demand = await self._demand_source()

        for market_id in list(self._subs):
            if market_id not in demand:
                await self._close(market_id)

        active = sum(1 for sub in self._subs.values() if sub.state != "closed")
        for market_id in sorted(demand):
            if market_id in self._subs:
                self._capacity_blocked.discard(market_id)
                continue
            if active >= self._max:
                self._capacity_blocked.add(market_id)
                continue
            self._capacity_blocked.discard(market_id)
            await self._start(market_id)
            active += 1

        for sub in list(self._subs.values()):
            if sub.state == "reconnecting":
                await self._rest_reconcile(sub, reason="reconnect", record_gap=True)
            elif sub.needs_reconcile:
                await self._rest_reconcile(
                    sub, reason="queue_overflow", record_gap=True
                )
            elif await self._deps.publisher.get_hot_book(sub.market_id) is None:
                await self._rest_reconcile(
                    sub, reason="hot_state_lost", record_gap=False
                )
            await self._pump(sub)

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

    async def _start(self, market_id: str) -> None:
        tokens = await self._token_lookup(market_id)
        rest_state = await self._deps.rest.get_order_book(market_id)
        player_tokens = {
            book.outcome_player_id: token
            for book, token in zip(rest_state.books, tokens, strict=True)
        }
        reducer = MarketBookReducer(
            market_id=market_id,
            token_players={token: player for player, token in player_tokens.items()},
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
            if self._metrics is not None:
                self._metrics.increment("decision_suppressed")

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
