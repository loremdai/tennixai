"""Bounded async TTL cache with in-flight coalescing and stale fallback.

Value-based TTL callables let empty or missing results use a short negative
TTL without a second cache type. The cache is process-local by design: P1 has
no Redis or multi-worker coordination.
"""

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class CacheOutcome(Generic[V]):
    value: V
    is_stale: bool
    age_seconds: int


@dataclass
class _Entry(Generic[V]):
    value: V
    loaded_at: float
    ttl: int


class AsyncTTLCache(Generic[K, V]):
    def __init__(self, max_entries: int, now: Callable[[], float] = monotonic) -> None:
        self._max_entries = max_entries
        self._now = now
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._inflight: dict[K, asyncio.Task[V]] = {}

    async def get_or_load(
        self,
        key: K,
        loader: Callable[[], Awaitable[V]],
        *,
        ttl: int | Callable[[V], int],
        stale_ttl: int | Callable[[V], int],
    ) -> CacheOutcome[V]:
        current = self._entries.get(key)
        if current is not None:
            age = max(0.0, self._now() - current.loaded_at)
            if age <= current.ttl:
                self._entries.move_to_end(key)
                return CacheOutcome(current.value, False, int(age))

        task = self._inflight.get(key)
        if task is None:
            async def load_and_store() -> V:
                value = await loader()
                resolved_ttl = ttl(value) if callable(ttl) else ttl
                self._entries[key] = _Entry(value=value, loaded_at=self._now(), ttl=resolved_ttl)
                self._entries.move_to_end(key)
                while len(self._entries) > self._max_entries:
                    self._entries.popitem(last=False)
                return value

            task = asyncio.create_task(load_and_store())
            self._inflight[key] = task

            def remove_inflight(done: asyncio.Task[V]) -> None:
                if self._inflight.get(key) is done:
                    self._inflight.pop(key, None)

            task.add_done_callback(remove_inflight)

        try:
            value = await asyncio.shield(task)
        except Exception:
            current = self._entries.get(key)
            if current is None:
                raise
            age = max(0.0, self._now() - current.loaded_at)
            resolved_stale_ttl = stale_ttl(current.value) if callable(stale_ttl) else stale_ttl
            if age > resolved_stale_ttl:
                raise
            self._entries.move_to_end(key)
            return CacheOutcome(current.value, True, int(age))

        stored = self._entries[key]
        return CacheOutcome(value, False, int(max(0.0, self._now() - stored.loaded_at)))
