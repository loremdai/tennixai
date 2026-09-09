"""Deterministic fakes for realtime tests: clock, Redis, feed, stores."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from app.domain import MatchSnapshot
from app.providers.base import ProviderLiveEnvelope
from app.realtime.models import LiveReduction


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def utcnow(self) -> datetime:
        return datetime.fromtimestamp(self._now, tz=timezone.utc)

    def advance(self, seconds: float) -> None:
        self._now += seconds


class InMemoryRedis:
    """Minimal async Redis subset with clock-driven expiry and pub/sub."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self._strings: dict[str, tuple[str, float | None]] = {}
        self._sets: dict[str, set[str]] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._channels: dict[str, list[asyncio.Queue]] = {}

    def _alive(self, entry: tuple[str, float | None]) -> bool:
        value, expires_at = entry
        if expires_at is not None and self._clock.now() >= expires_at:
            return False
        return True

    async def set(self, name: str, value: str, ex: float | None = None) -> None:
        expires_at = self._clock.now() + ex if ex is not None else None
        self._strings[name] = (value, expires_at)

    async def get(self, name: str) -> str | None:
        entry = self._strings.get(name)
        if entry is None or not self._alive(entry):
            self._strings.pop(name, None)
            return None
        return entry[0]

    async def delete(self, *names: str) -> None:
        for name in names:
            self._strings.pop(name, None)

    async def sadd(self, name: str, *values: str) -> None:
        self._sets.setdefault(name, set()).update(values)

    async def srem(self, name: str, *values: str) -> None:
        bucket = self._sets.get(name)
        if bucket is None:
            return
        bucket.difference_update(values)
        if not bucket:
            self._sets.pop(name, None)

    async def smembers(self, name: str) -> set[str]:
        return set(self._sets.get(name, ()))

    async def hset(self, name: str, key: str | None = None, value: str | None = None, mapping: dict[str, str] | None = None) -> None:
        bucket = self._hashes.setdefault(name, {})
        if key is not None and value is not None:
            bucket[key] = value
        if mapping:
            bucket.update(mapping)

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    async def hdel(self, name: str, *keys: str) -> None:
        bucket = self._hashes.get(name)
        if bucket is None:
            return
        for key in keys:
            bucket.pop(key, None)
        if not bucket:
            self._hashes.pop(name, None)

    async def publish(self, channel: str, message: str) -> None:
        for queue in self._channels.get(channel, []):
            queue.put_nowait(message)

    def pubsub(self) -> "InMemoryPubSub":
        return InMemoryPubSub(self)


class InMemoryPubSub:
    def __init__(self, redis: InMemoryRedis) -> None:
        self._redis = redis
        self._queues: dict[str, asyncio.Queue] = {}

    async def subscribe(self, channel: str) -> None:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[channel] = queue
        self._redis._channels.setdefault(channel, []).append(queue)

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float | None = None):
        for queue in self._queues.values():
            try:
                message = queue.get_nowait()
                return {"type": "message", "data": message}
            except asyncio.QueueEmpty:
                continue
        if timeout:
            await asyncio.sleep(min(timeout, 0.01))
        return None

    async def aclose(self) -> None:
        for channel, queue in self._queues.items():
            buckets = self._redis._channels.get(channel, [])
            if queue in buckets:
                buckets.remove(queue)


DISCONNECT = object()
END = object()


class FakeLiveFeed:
    """Scripted per-match feed implementing the live-feed protocol."""

    def __init__(self) -> None:
        self.opened_external_ids: list[str] = []
        self.closed_external_ids: list[str] = []
        self._queues: dict[str, asyncio.Queue] = {}

    def _queue(self, external_id: str) -> asyncio.Queue:
        return self._queues.setdefault(external_id, asyncio.Queue())

    async def push(self, external_id: str, envelope: ProviderLiveEnvelope) -> None:
        self._queue(external_id).put_nowait(envelope)

    async def disconnect(self, external_id: str) -> None:
        self._queue(external_id).put_nowait(DISCONNECT)

    async def end(self, external_id: str) -> None:
        self._queue(external_id).put_nowait(END)

    def stream_match(self, external_match_id: str):
        feed = self
        feed.opened_external_ids.append(external_match_id)
        # A new stream is a new connection: queued frames from a previous
        # connection are gone, mirroring real WebSocket semantics.
        queue: asyncio.Queue = asyncio.Queue()
        feed._queues[external_match_id] = queue

        async def generator():
            try:
                while True:
                    item = await queue.get()
                    if item is DISCONNECT:
                        from app.realtime.models import FeedDisconnected

                        raise FeedDisconnected("peer_closed")
                    if item is END:
                        return
                    yield item
            finally:
                feed.closed_external_ids.append(external_match_id)

        return generator()

    async def to_candidate(self, envelope: ProviderLiveEnvelope) -> MatchSnapshot | None:
        payload = envelope.payload.get("snapshot")
        if payload is None:
            return None
        return MatchSnapshot.model_validate(payload)


def snapshot_envelope(snapshot: MatchSnapshot, received_at: datetime) -> ProviderLiveEnvelope:
    return ProviderLiveEnvelope(
        external_match_id="ext-of-envelope",
        provider="api_tennis",
        channel="websocket",
        kind="snapshot",
        received_at=received_at,
        payload={"snapshot": json.loads(snapshot.model_dump_json())},
    )


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self.saved: list[LiveReduction] = []
        self.current: dict[str, MatchSnapshot] = {}

    async def save_reduction(self, reduction: LiveReduction) -> None:
        self.saved.append(reduction)
        self.current[reduction.match_id] = reduction.snapshot

    async def get_current_state(self, match_id: str):
        snapshot = self.current.get(match_id)
        if snapshot is None or snapshot.match.live_state is None:
            return None
        return snapshot.match.live_state, snapshot.as_of

    async def get_snapshot(self, match_id: str) -> MatchSnapshot | None:
        return self.current.get(match_id)


class FakeRestProvider:
    def __init__(self, snapshots: list[MatchSnapshot]) -> None:
        self._snapshots = list(snapshots)
        self.calls = 0

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        self.calls += 1
        if not self._snapshots:
            raise AssertionError("no scripted REST snapshot left")
        if len(self._snapshots) == 1:
            return self._snapshots[0]
        return self._snapshots.pop(0)


class FakeRawRepository:
    def __init__(self) -> None:
        self.purged_before: list[datetime] = []

    async def purge_raw_events(self, before: datetime) -> int:
        self.purged_before.append(before)
        return 0
