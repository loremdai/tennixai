"""Realtime worker: shared upstream, lifecycle, capacity, reconnect, retention."""

from datetime import datetime, timedelta, timezone

import pytest

from realtime_fakes import (
    FakeClock,
    FakeLiveFeed,
    FakeRawRepository,
    FakeRestProvider,
    InMemoryRedis,
    InMemorySnapshotStore,
    snapshot_envelope,
)

from app.domain import (
    CapabilityStatus,
    DataFreshness,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    MatchStatus,
    Player,
    PointEvent,
    SetScore,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.identity import MemoryIdentityRepository
from app.realtime.leases import ViewerLeaseStore
from app.realtime.publisher import RealtimePublisher
from app.realtime.worker import RealtimeWorker

PROVIDER = "api_tennis"
EXTERNAL = "11997372"
LEASE_SECONDS = 45
GRACE_SECONDS = 60
_START = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def NOW() -> datetime:
    return _START


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def redis(clock: FakeClock) -> InMemoryRedis:
    return InMemoryRedis(clock)


@pytest.fixture()
def leases(redis: InMemoryRedis, clock: FakeClock) -> ViewerLeaseStore:
    return ViewerLeaseStore(
        redis,
        lease_seconds=LEASE_SECONDS,
        grace_seconds=GRACE_SECONDS,
        now=clock.now,
    )


def base_match(match_id: str, status: MatchStatus = MatchStatus.LIVE) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=(Player(id="ply_a", name="A"), Player(id="ply_b", name="B")),
        tournament=Tournament(id="trn_t", name="Tulln"),
        live_state=LiveMatchState(
            score=MatchScore(
                sets_won=(1, 1),
                sets=(SetScore(number=3, player1_games=2, player2_games=2),),
                points=("30", "15"),
            ),
            server_player_id="ply_a",
            state_version=0,
        ),
        freshness=DataFreshness(provider=PROVIDER, observed_at=NOW()),
    )


def point(match_id: str, sequence: int) -> PointEvent:
    return PointEvent(
        id=f"pe_{match_id}_{sequence}",
        match_id=match_id,
        sequence=sequence,
        set_number=3,
        game_number=1,
        point_number=sequence,
        server_player_id="ply_a",
        winner_player_id="ply_a",
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
        observed_at=NOW(),
        provider=PROVIDER,
        source_fingerprint=f"fp-{sequence}",
    )


def candidate(
    match_id: str,
    *,
    points: int = 0,
    status: MatchStatus = MatchStatus.LIVE,
) -> MatchSnapshot:
    return MatchSnapshot(
        match=base_match(match_id, status),
        points=tuple(point(match_id, i) for i in range(1, points + 1)),
        statistics=(),
        momentum=(),
        quality=(),
        state_version=0,
        as_of=NOW(),
    )


@pytest.fixture()
def identity() -> MemoryIdentityRepository:
    return MemoryIdentityRepository()


async def match_id(identity: MemoryIdentityRepository) -> str:
    return await identity.get_or_create("match", PROVIDER, EXTERNAL)


def make_worker(
    *,
    identity: MemoryIdentityRepository,
    clock: FakeClock,
    leases: ViewerLeaseStore,
    rest: FakeRestProvider,
    max_live_subscriptions: int = 8,
):
    store = InMemorySnapshotStore()
    publisher = RealtimePublisher(InMemoryRedis(clock), now=clock.utcnow)
    feed = FakeLiveFeed()
    raw = FakeRawRepository()
    worker = RealtimeWorker(
        identity=identity,
        snapshots=store,
        leases=leases,
        publisher=publisher,
        feed=feed,
        rest=rest,
        raw=raw,
        now=clock.utcnow,
        max_live_subscriptions=max_live_subscriptions,
    )
    return worker, store, publisher, feed, raw


@pytest.mark.asyncio
async def test_two_viewers_share_one_upstream_subscription(identity, leases, clock) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
    )

    await leases.acquire(match, "viewer_a")
    await leases.acquire(match, "viewer_b")
    await worker.reconcile_demand_once()
    await worker.reconcile_demand_once()

    assert feed.opened_external_ids == [EXTERNAL]
    assert len(store.saved) == 1
    assert store.saved[0].snapshot.state_version == 1
    await worker.stop()


@pytest.mark.asyncio
async def test_rest_initial_snapshot_persists_before_stream_envelopes(
    identity, leases, clock
) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
    )

    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()

    assert worker._rest.calls == 1
    assert store.saved[0].snapshot.state_version == 1
    assert [event["type"] for event in publisher.events] == ["match_delta"]
    assert publisher.events[0]["state_version"] == 1

    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=2), NOW()))
    await worker.reconcile_demand_once()

    assert len(store.saved) == 2
    assert store.saved[1].snapshot.state_version == 2
    assert publisher.events[1]["state_version"] == 2
    await worker.stop()


@pytest.mark.asyncio
async def test_grace_expiry_closes_the_upstream_feed(identity, leases, clock) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
    )

    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()
    assert feed.opened_external_ids == [EXTERNAL]

    await leases.release(match, "viewer_a")
    await worker.reconcile_demand_once()
    assert feed.closed_external_ids == []

    clock.advance(GRACE_SECONDS)
    await worker.reconcile_demand_once()
    assert feed.closed_external_ids == [EXTERNAL]
    assert worker.subscription_state(match) == "closed"
    await worker.stop()


@pytest.mark.asyncio
async def test_hidden_viewer_lease_expiry_closes_feed(identity, leases, clock) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
    )

    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()
    clock.advance(LEASE_SECONDS)
    await worker.reconcile_demand_once()

    assert feed.closed_external_ids == [EXTERNAL]
    await worker.stop()


@pytest.mark.asyncio
async def test_capacity_limited_blocks_extra_subscriptions(identity, leases, clock) -> None:
    match = await match_id(identity)
    second = await identity.get_or_create("match", PROVIDER, "12161239")
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1), candidate(second, points=1)]),
        max_live_subscriptions=1,
    )

    await leases.acquire(match, "viewer_a")
    await leases.acquire(second, "viewer_b")
    await worker.reconcile_demand_once()

    assert feed.opened_external_ids == [EXTERNAL]
    assert worker.subscription_state(second) == "capacity_limited"
    await worker.stop()


@pytest.mark.asyncio
async def test_reconnect_reconciles_via_rest_before_later_ws_deltas(
    identity, leases, clock
) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1), candidate(match, points=3)]),
    )

    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()  # v1 REST initial (1 point)

    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=2), NOW()))
    await worker.reconcile_demand_once()  # v2 WS append

    await feed.disconnect(EXTERNAL)
    # Envelope queued before the disconnect is stale and must be dropped.
    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=2), NOW()))
    await worker.reconcile_demand_once()  # detects disconnect -> REST reconcile v3
    await worker.reconcile_demand_once()  # stale queued envelope dropped, no change

    versions = [reduction.snapshot.state_version for reduction in store.saved]
    assert versions == [1, 2, 3]
    assert len(store.saved[2].snapshot.points) == 3
    assert worker._rest.calls == 2

    # Post-reconnect WS deltas resume after the REST reconciliation.
    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=4), NOW()))
    await worker.reconcile_demand_once()
    versions = [reduction.snapshot.state_version for reduction in store.saved]
    assert versions == [1, 2, 3, 4]
    assert len(store.saved[3].snapshot.points) == 4
    await worker.stop()


@pytest.mark.asyncio
async def test_terminal_state_closes_immediately_and_publishes_match_ended(
    identity, leases, clock
) -> None:
    match = await match_id(identity)
    worker, store, publisher, feed, raw = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
    )

    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()
    await feed.push(
        EXTERNAL,
        snapshot_envelope(candidate(match, points=2, status=MatchStatus.FINISHED), NOW()),
    )
    await worker.reconcile_demand_once()

    assert [event["type"] for event in publisher.events][-1] == "match_ended"
    assert feed.closed_external_ids == [EXTERNAL]
    assert worker.subscription_state(match) == "closed"
    # Lease is still active: terminal close does not wait for grace.
    assert [item.state for item in await leases.demanded_matches()] == ["active"]
    await worker.stop()


@pytest.mark.asyncio
async def test_retention_cleanup_uses_the_14_day_cutoff(identity, clock) -> None:
    redis = InMemoryRedis(clock)
    leases = ViewerLeaseStore(
        redis, lease_seconds=LEASE_SECONDS, grace_seconds=GRACE_SECONDS, now=clock.now
    )
    worker, store, publisher, feed, raw = make_worker(
        identity=identity, clock=clock, leases=leases, rest=FakeRestProvider([])
    )

    await worker.cleanup_raw_events()

    assert raw.purged_before == [clock.utcnow() - timedelta(days=14)]
    await worker.stop()
