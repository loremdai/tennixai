"""Viewer lease semantics: TTL, renewal, grace and demand index."""

import pytest

from realtime_fakes import FakeClock, InMemoryRedis

from app.realtime.leases import ViewerLeaseStore

LEASE_SECONDS = 45
GRACE_SECONDS = 60


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def redis(clock: FakeClock) -> InMemoryRedis:
    return InMemoryRedis(clock)


@pytest.fixture()
def leases(redis: InMemoryRedis) -> ViewerLeaseStore:
    return ViewerLeaseStore(
        redis,
        lease_seconds=LEASE_SECONDS,
        grace_seconds=GRACE_SECONDS,
        now=lambda: datetime_now(redis),
    )


def datetime_now(redis: InMemoryRedis) -> float:
    return redis._clock.now()


@pytest.mark.asyncio
async def test_acquire_creates_active_demand(leases: ViewerLeaseStore) -> None:
    await leases.acquire("mat_live", "viewer_a")

    demanded = await leases.demanded_matches()
    assert [(item.match_id, item.state) for item in demanded] == [("mat_live", "active")]


@pytest.mark.asyncio
async def test_renew_extends_the_lease_ttl(
    leases: ViewerLeaseStore, redis: InMemoryRedis
) -> None:
    await leases.acquire("mat_live", "viewer_a")
    redis._clock.advance(LEASE_SECONDS - 1)
    await leases.renew("mat_live", "viewer_a")
    redis._clock.advance(LEASE_SECONDS - 1)

    demanded = await leases.demanded_matches()
    assert [item.match_id for item in demanded] == ["mat_live"]


@pytest.mark.asyncio
async def test_unrenewed_lease_expires_and_is_pruned(
    leases: ViewerLeaseStore, redis: InMemoryRedis
) -> None:
    await leases.acquire("mat_live", "viewer_a")
    redis._clock.advance(LEASE_SECONDS)

    assert await leases.demanded_matches() == []
    # The demand index no longer references the expired match.
    assert await redis.smembers("tnx:demand") == set()


@pytest.mark.asyncio
async def test_last_release_starts_grace_then_expires(
    leases: ViewerLeaseStore, redis: InMemoryRedis
) -> None:
    await leases.acquire("mat_live", "viewer_a")
    await leases.acquire("mat_live", "viewer_b")

    await leases.release("mat_live", "viewer_a")
    demanded = await leases.demanded_matches()
    assert [(item.match_id, item.state) for item in demanded] == [("mat_live", "active")]

    await leases.release("mat_live", "viewer_b")
    demanded = await leases.demanded_matches()
    assert [(item.match_id, item.state) for item in demanded] == [("mat_live", "grace")]

    redis._clock.advance(GRACE_SECONDS - 1)
    assert [item.state for item in await leases.demanded_matches()] == ["grace"]

    redis._clock.advance(1)
    assert await leases.demanded_matches() == []


@pytest.mark.asyncio
async def test_reacquire_during_grace_returns_to_active(
    leases: ViewerLeaseStore, redis: InMemoryRedis
) -> None:
    await leases.acquire("mat_live", "viewer_a")
    await leases.release("mat_live", "viewer_a")
    assert [item.state for item in await leases.demanded_matches()] == ["grace"]

    await leases.acquire("mat_live", "viewer_c")
    assert [item.state for item in await leases.demanded_matches()] == ["active"]


@pytest.mark.asyncio
async def test_release_of_unknown_viewer_is_a_noop(leases: ViewerLeaseStore) -> None:
    await leases.acquire("mat_live", "viewer_a")
    await leases.release("mat_live", "viewer_ghost")

    assert [item.state for item in await leases.demanded_matches()] == ["active"]
