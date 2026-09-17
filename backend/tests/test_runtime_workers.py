"""Composed runtime worker tests (T77).

One upstream subscription per match regardless of how many demand sources
want it, `RealtimeWorker` hooks (`demand_source`, post-commit `on_snapshot`,
stable-value `on_connection`) with isolated callback failures, and
`MarketWorker.active_market_ids()` plus `on_state` after REST baselines.
Existing P2/P3 behavior with default (None) hooks stays untouched and is
proven by the original worker test modules.
"""

import asyncio
import json

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
from test_market_worker import (
    MKT_1,
    DemandSource,
    FakeMarketFeed,
    FakeObservationSink,
    FakePublisher,
    FakeRaw,
    FakeRest,
    book_event,
    token_lookup,
)
from test_market_worker import FakeClock as MarketFakeClock
from test_realtime_worker import NOW, candidate

from app.identity import MemoryIdentityRepository
from app.markets.worker import MarketWorker
from app.realtime.leases import ViewerLeaseStore
from app.realtime.p3_metrics import P3Metrics
from app.realtime.publisher import RealtimePublisher
from app.realtime.worker import RealtimeWorker

PROVIDER = "api_tennis"
EXTERNAL = "match_external_1"


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def leases(clock: FakeClock) -> ViewerLeaseStore:
    return ViewerLeaseStore(
        InMemoryRedis(clock), lease_seconds=45, grace_seconds=60, now=clock.now
    )


async def internal_match_id() -> tuple[MemoryIdentityRepository, str]:
    identity = MemoryIdentityRepository()
    return identity, await identity.get_or_create("match", PROVIDER, EXTERNAL)


def make_worker(
    *,
    identity: MemoryIdentityRepository,
    clock: FakeClock,
    leases: ViewerLeaseStore,
    rest: FakeRestProvider,
    demand_source=None,
    on_snapshot=None,
    on_connection=None,
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
        max_live_subscriptions=8,
        demand_source=demand_source,
        on_snapshot=on_snapshot,
        on_connection=on_connection,
    )
    return worker, store, publisher, feed


# ---------------------------------------------------------------------------
# Composed demand: one upstream subscription per match
# ---------------------------------------------------------------------------


async def test_runtime_opens_one_sports_subscription_when_viewer_and_p3_need_same_match(
    clock, leases
):
    identity, match = await internal_match_id()

    async def paper_demand() -> dict[str, str]:
        return {match: "active"}

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
        demand_source=paper_demand,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()

    # Viewer lease and durable P3 demand collapse to ONE upstream feed.
    assert feed.opened_external_ids == [EXTERNAL]
    assert worker.subscription_state(match) == "live"
    await worker.stop()


async def test_p3_demand_alone_keeps_upstream_alive_with_zero_viewers(clock, leases):
    identity, match = await internal_match_id()
    tracked = {match: "active"}

    async def paper_demand() -> dict[str, str]:
        return dict(tracked)

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
        demand_source=paper_demand,
    )
    await worker.reconcile_demand_once()
    assert feed.opened_external_ids == [EXTERNAL]

    tracked.clear()
    await worker.reconcile_demand_once()
    assert feed.closed_external_ids == [EXTERNAL]
    assert worker.subscription_state(match) == "closed"
    await worker.stop()


async def test_lease_active_state_is_never_downgraded_by_demand_source(clock, leases):
    identity, match = await internal_match_id()

    async def stale_source() -> dict[str, str]:
        return {match: "grace"}

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
        demand_source=stale_source,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()

    assert feed.opened_external_ids == [EXTERNAL]
    await worker.stop()


# ---------------------------------------------------------------------------
# on_snapshot: post-commit only, error-isolated
# ---------------------------------------------------------------------------


async def test_on_snapshot_fires_only_after_canonical_commit(clock, leases):
    identity, match = await internal_match_id()
    calls: list[tuple[str, int, int, int]] = []

    async def on_snapshot(match_id, snapshot):
        calls.append(
            (match_id, snapshot.state_version, len(store.saved), len(publisher.events))
        )

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
        on_snapshot=on_snapshot,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()

    # The hook sees the committed snapshot only after persistence and P2
    # publication already happened.
    assert calls == [(match, 1, 1, 1)]
    assert calls[0][1] == store.saved[0].snapshot.state_version

    # An unchanged duplicate reduction never commits, so the hook stays idle.
    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=1), NOW()))
    await worker.reconcile_demand_once()
    assert len(calls) == 1
    assert len(store.saved) == 1
    await worker.stop()


async def test_on_snapshot_failure_is_isolated_counted_and_never_blocks_p2(
    clock, leases
):
    identity, match = await internal_match_id()

    async def failing_snapshot(match_id, snapshot):
        raise RuntimeError("downstream_failed")

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1)]),
        on_snapshot=failing_snapshot,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()

    assert len(store.saved) == 1
    assert publisher.events[0]["type"] == "match_delta"
    assert worker.callback_failures["on_snapshot"] == 1

    # Later cycles keep persisting and publishing despite the failing hook.
    await feed.push(EXTERNAL, snapshot_envelope(candidate(match, points=2), NOW()))
    await worker.reconcile_demand_once()
    assert len(store.saved) == 2
    assert publisher.events[1]["type"] == "match_delta"
    assert worker.callback_failures["on_snapshot"] == 2
    await worker.stop()


# ---------------------------------------------------------------------------
# on_connection: stable values at reconnect and healthy recovery
# ---------------------------------------------------------------------------


async def test_on_connection_reports_stable_reconnect_and_recovery_values(
    clock, leases
):
    identity, match = await internal_match_id()
    events: list[tuple[str, str]] = []

    async def on_connection(match_id, state):
        events.append((match_id, state))

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1), candidate(match, points=3)]),
        on_connection=on_connection,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()
    assert events == []  # initial subscribe is not a connection transition

    await feed.disconnect(EXTERNAL)
    await worker.reconcile_demand_once()

    assert events == [(match, "reconnecting"), (match, "live")]
    await worker.stop()


async def test_on_connection_failure_is_isolated_and_counted(clock, leases):
    identity, match = await internal_match_id()

    async def failing_connection(match_id, state):
        raise RuntimeError("downstream_failed")

    worker, store, publisher, feed = make_worker(
        identity=identity,
        clock=clock,
        leases=leases,
        rest=FakeRestProvider([candidate(match, points=1), candidate(match, points=3)]),
        on_connection=failing_connection,
    )
    await leases.acquire(match, "viewer_a")
    await worker.reconcile_demand_once()
    await feed.disconnect(EXTERNAL)
    await worker.reconcile_demand_once()

    connection_states = [
        event.get("connection_status")
        for event in publisher.events
        if "connection_status" in event
    ]
    assert connection_states == ["reconnecting", "live"]
    assert worker.callback_failures["on_connection"] == 2
    assert worker.subscription_state(match) == "live"
    await worker.stop()


# ---------------------------------------------------------------------------
# MarketWorker: active_market_ids copy + on_state after REST baselines
# ---------------------------------------------------------------------------


def make_market_worker(clock, *, demand=None, on_state=None, metrics=None):
    parts = {
        "feed": FakeMarketFeed(),
        "rest": FakeRest(),
        "publisher": FakePublisher(),
        "sink": FakeObservationSink(),
        "raw": FakeRaw(),
        "demand": demand or DemandSource({MKT_1}),
    }
    worker = MarketWorker(
        feed=parts["feed"],
        rest=parts["rest"],
        publisher=parts["publisher"],
        observations=parts["sink"],
        raw=parts["raw"],
        demand_source=parts["demand"],
        token_lookup=token_lookup,
        now=clock.now,
        on_state=on_state,
        metrics=metrics,
    )
    return worker, parts


async def test_active_market_ids_returns_a_stable_copy():
    clock = MarketFakeClock()
    demand = DemandSource({MKT_1})
    worker, parts = make_market_worker(clock, demand=demand)

    assert worker.active_market_ids() == ()
    await worker.reconcile_demand_once()
    taken = worker.active_market_ids()
    assert taken == (MKT_1,)

    demand.markets = set()
    await worker.reconcile_demand_once()

    # The earlier copy never mutates; the fresh call reflects the close.
    assert taken == (MKT_1,)
    assert worker.active_market_ids() == ()
    await worker.stop()


async def test_on_state_receives_rest_baseline_before_any_ws_event():
    clock = MarketFakeClock()
    seen: list[tuple[str, str]] = []

    async def on_state(market_id, state):
        seen.append((market_id, state.book_hash))

    worker, parts = make_market_worker(clock, on_state=on_state)
    await worker.reconcile_demand_once()

    assert seen == [(MKT_1, f"rest_{MKT_1}")]

    # A changed WS book still reaches the hook (existing behavior).
    await parts["feed"].push(MKT_1, book_event(MKT_1, "h1", 1_789_999_200_000))
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()
    assert len(seen) == 2
    assert seen[1][0] == MKT_1
    await worker.stop()


async def test_on_state_receives_recovered_baseline_after_disconnect():
    clock = MarketFakeClock()
    seen: list[str] = []

    async def on_state(market_id, state):
        seen.append(market_id)

    worker, parts = make_market_worker(clock, on_state=on_state)
    await worker.reconcile_demand_once()
    assert seen == [MKT_1]

    await parts["feed"].disconnect(MKT_1)
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()

    assert seen == [MKT_1, MKT_1]
    assert worker.subscription_state(MKT_1) == "live"
    await worker.stop()


async def test_on_state_failure_after_baseline_is_counted_and_publish_survives():
    clock = MarketFakeClock()
    metrics = P3Metrics()

    async def failing_state(market_id, state):
        raise RuntimeError("downstream_failed")

    worker, parts = make_market_worker(clock, on_state=failing_state, metrics=metrics)
    await worker.reconcile_demand_once()

    assert MKT_1 in parts["publisher"].hot
    counters = json.loads(metrics.export())["counters"]
    assert counters.get("decision_suppressed") == 1
    await worker.stop()
