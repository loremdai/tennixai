import asyncio

import pytest

from app.cache import AsyncTTLCache, CacheOutcome


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.mark.asyncio
async def test_fresh_hit_does_not_call_loader_again() -> None:
    clock = FakeClock()
    calls = 0
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256, now=clock)

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return "value"

    first = await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)
    clock.advance(30)
    second = await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)

    assert calls == 1
    assert first == CacheOutcome("value", False, 0)
    assert second.value == "value"
    assert second.is_stale is False
    assert second.age_seconds == 30


@pytest.mark.asyncio
async def test_coalesces_identical_inflight_loads() -> None:
    calls = 0
    gate = asyncio.Event()
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256)

    async def loader() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "value"

    tasks = [
        asyncio.create_task(cache.get_or_load("key", loader, ttl=60, stale_ttl=300))
        for _ in range(3)
    ]
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks)

    assert calls == 1
    assert [result.value for result in results] == ["value", "value", "value"]
    assert all(result.is_stale is False for result in results)


@pytest.mark.asyncio
async def test_loader_failure_returns_marked_stale_within_stale_ttl() -> None:
    clock = FakeClock()
    attempts = 0
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256, now=clock)

    async def loader() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "value"
        raise RuntimeError("provider down")

    await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)
    clock.advance(120)

    stale = await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)
    assert stale == CacheOutcome("value", True, 120)


@pytest.mark.asyncio
async def test_loader_failure_reraises_beyond_stale_ttl() -> None:
    clock = FakeClock()
    attempts = 0
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256, now=clock)

    async def loader() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "value"
        raise RuntimeError("provider down")

    await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)
    clock.advance(301)

    with pytest.raises(RuntimeError, match="provider down"):
        await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)


@pytest.mark.asyncio
async def test_loader_failure_without_entry_propagates() -> None:
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256)

    async def loader() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await cache.get_or_load("key", loader, ttl=60, stale_ttl=300)


@pytest.mark.asyncio
async def test_lru_eviction_at_max_entries() -> None:
    clock = FakeClock()
    cache: AsyncTTLCache[str, int] = AsyncTTLCache(max_entries=256, now=clock)

    async def make_loader(value: int):
        async def loader() -> int:
            return value

        return loader

    for index in range(256):
        loader = await make_loader(index)
        await cache.get_or_load(f"key-{index}", loader, ttl=60, stale_ttl=0)

    # Touch key-0 so key-1 becomes the least recently used entry.
    loader_zero = await make_loader(0)
    await cache.get_or_load("key-0", loader_zero, ttl=60, stale_ttl=0)

    loader_new = await make_loader(999)
    await cache.get_or_load("key-256", loader_new, ttl=60, stale_ttl=0)

    calls = 0

    async def counting_loader() -> int:
        nonlocal calls
        calls += 1
        return -1

    await cache.get_or_load("key-1", counting_loader, ttl=60, stale_ttl=0)
    assert calls == 1, "key-1 should have been evicted"

    calls = 0
    await cache.get_or_load("key-0", counting_loader, ttl=60, stale_ttl=0)
    assert calls == 0, "key-0 should still be cached"


@pytest.mark.asyncio
async def test_value_based_ttl_callables_support_negative_cache() -> None:
    clock = FakeClock()
    calls = 0
    cache: AsyncTTLCache[str, list[str]] = AsyncTTLCache(max_entries=256, now=clock)

    async def loader() -> list[str]:
        nonlocal calls
        calls += 1
        return []

    ttl = lambda value: 30 if not value else 3600  # noqa: E731
    stale_ttl = lambda value: 0 if not value else 300  # noqa: E731

    await cache.get_or_load("players:nobody", loader, ttl=ttl, stale_ttl=stale_ttl)
    clock.advance(15)
    await cache.get_or_load("players:nobody", loader, ttl=ttl, stale_ttl=stale_ttl)
    assert calls == 1, "empty result stays fresh for 30 seconds"

    clock.advance(16)
    await cache.get_or_load("players:nobody", loader, ttl=ttl, stale_ttl=stale_ttl)
    assert calls == 2, "empty result expires after 30 seconds"


@pytest.mark.asyncio
async def test_expired_fresh_entry_reloads_and_stores_new_value() -> None:
    clock = FakeClock()
    values = iter(["first", "second"])
    cache: AsyncTTLCache[str, str] = AsyncTTLCache(max_entries=256, now=clock)

    async def loader() -> str:
        return next(values)

    first = await cache.get_or_load("key", loader, ttl=60, stale_ttl=0)
    clock.advance(61)
    second = await cache.get_or_load("key", loader, ttl=60, stale_ttl=0)

    assert first.value == "first"
    assert second == CacheOutcome("second", False, 0)
