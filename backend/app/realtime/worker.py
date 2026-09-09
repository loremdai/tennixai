"""Realtime worker: on-demand upstream subscriptions with REST reconcile.

One upstream feed per demanded match, viewer leases drive demand, reductions
are persisted before publication, and raw payloads are purged on schedule.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from app.domain import MatchSnapshot, MatchStatus
from app.identity import IdentityRepository
from app.realtime.leases import ViewerLeaseStore
from app.realtime.models import FeedDisconnected, LiveReduction
from app.realtime.publisher import RealtimePublisher
from app.realtime.reducer import reduce_live_snapshot

PROVIDER_NAME = "api_tennis"
RAW_RETENTION_DAYS = 14


class Subscription:
    def __init__(self, match_id: str, external_id: str, feed) -> None:
        self.match_id = match_id
        self.external_id = external_id
        self._feed = feed
        self._stream = feed.stream_match(external_id)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.state = "live"  # live | reconnecting | terminal | closed
        self.disconnect_detected = False
        self._reader: asyncio.Task | None = None

    async def start_reader(self) -> None:
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            async for envelope in self._stream:
                if envelope.kind == "disconnect":
                    self.disconnect_detected = True
                    return
                await self.queue.put(envelope)
        except asyncio.CancelledError:
            raise
        except FeedDisconnected:
            self.disconnect_detected = True
        except Exception:
            # Any transport failure is a disconnect; reconnecting is the
            # worker's job and diagnostics never carry connection URIs.
            self.disconnect_detected = True

    async def restart_reader(self) -> None:
        self._stream = self._feed.stream_match(self.external_id)
        await self.start_reader()

    async def close(self) -> None:
        self.state = "closed"
        if self._reader is not None and not self._reader.done():
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        self._reader = None


class RealtimeWorker:
    def __init__(
        self,
        *,
        identity: IdentityRepository,
        snapshots,
        leases: ViewerLeaseStore,
        publisher: RealtimePublisher,
        feed,
        rest,
        raw,
        now: Callable[[], datetime],
        max_live_subscriptions: int,
        provider_name: str = PROVIDER_NAME,
    ) -> None:
        self._identity = identity
        self._snapshots = snapshots
        self._leases = leases
        self._publisher = publisher
        self._feed = feed
        self._rest = rest
        self._raw = raw
        self._now = now
        self._max = max_live_subscriptions
        self._provider_name = provider_name
        self._subs: dict[str, Subscription] = {}
        self._capacity_blocked: set[str] = set()
        self._current: dict[str, MatchSnapshot] = {}

    def subscription_state(self, match_id: str) -> str:
        sub = self._subs.get(match_id)
        if sub is not None:
            return sub.state
        if match_id in self._capacity_blocked:
            return "capacity_limited"
        return "closed"

    async def reconcile_demand_once(self) -> None:
        # Let reader tasks surface queued frames/disconnects before pumping.
        await asyncio.sleep(0)
        demanded = {
            item.match_id: item.state for item in await self._leases.demanded_matches()
        }

        for match_id in list(self._subs):
            if match_id not in demanded:
                await self._close(match_id)

        active = sum(
            1 for sub in self._subs.values() if sub.state in ("live", "reconnecting")
        )
        for match_id, state in demanded.items():
            if match_id in self._subs:
                continue
            if state != "active":
                continue
            if active >= self._max:
                self._capacity_blocked.add(match_id)
                continue
            self._capacity_blocked.discard(match_id)
            external_id = await self._identity.external_id(
                "match", self._provider_name, match_id
            )
            if external_id is None:
                continue
            sub = Subscription(match_id, external_id, self._feed)
            self._subs[match_id] = sub
            # REST snapshot first: the stream only ever carries deltas onto it.
            await self._rest_reconcile(match_id, recovery=False)
            await sub.start_reader()
            active += 1

        for match_id, sub in list(self._subs.items()):
            if sub.state == "closed":
                continue
            if sub.disconnect_detected:
                sub.disconnect_detected = False
                sub.state = "reconnecting"
                await self._publisher.publish_connection(
                    match_id, "reconnecting", self._now()
                )
                while not sub.queue.empty():
                    sub.queue.get_nowait()
                await self._rest_reconcile(match_id, recovery=True)
                await sub.restart_reader()
                sub.state = "live"
                await self._publisher.publish_connection(match_id, "live", self._now())
                continue
            while not sub.queue.empty():
                envelope = sub.queue.get_nowait()
                candidate = await self._feed.to_candidate(envelope)
                if candidate is None:
                    continue
                await self._apply(match_id, candidate)
                if candidate.match.status is MatchStatus.FINISHED:
                    current = self._current.get(match_id)
                    version = current.state_version if current else 0
                    as_of = current.as_of if current else candidate.as_of
                    await self._publisher.publish_match_ended(match_id, version, as_of)
                    sub.state = "terminal"
                    await self._close(match_id)
                    break

    async def _apply(self, match_id: str, candidate: MatchSnapshot) -> LiveReduction | None:
        previous = self._current.get(match_id)
        reduction = reduce_live_snapshot(previous, candidate)
        if not reduction.changed:
            return None
        await self._snapshots.save_reduction(reduction)
        self._current[match_id] = reduction.snapshot
        await self._publisher.publish_delta(reduction)
        return reduction

    async def _rest_reconcile(self, match_id: str, *, recovery: bool) -> None:
        if match_id not in self._current:
            loader = getattr(self._snapshots, "load_snapshot", None)
            if loader is not None:
                persisted = await loader(match_id)
                if persisted is not None:
                    self._current[match_id] = persisted
        reconcile = getattr(self._rest, "reconcile_match_snapshot", None)
        if reconcile is not None:
            candidate = await reconcile(match_id, recovery=recovery)
        else:
            candidate = await self._rest.get_match_snapshot(match_id)
        await self._apply(match_id, candidate)

    async def _close(self, match_id: str) -> None:
        sub = self._subs.pop(match_id, None)
        if sub is not None:
            await sub.close()

    async def cleanup_raw_events(self) -> int:
        cutoff = self._now() - timedelta(days=RAW_RETENTION_DAYS)
        return await self._raw.purge_raw_events(cutoff)

    async def stop(self) -> None:
        for match_id in list(self._subs):
            await self._close(match_id)

    async def run_forever(self, *, interval_seconds: float = 0.1) -> None:
        """Run demand reconciliation until the host process cancels the task."""

        while True:
            await self.reconcile_demand_once()
            await asyncio.sleep(interval_seconds)
