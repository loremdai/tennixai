"""Market worker orchestration tests (T60).

Bounded per-market queues, dynamic subscribe/unsubscribe, no I/O inside the
receive callback, REST-first reconcile after disconnect, Redis hot-state
loss recovery, batched observation persistence, 14-day raw cleanup and a
deterministic replay feed.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path


from app.markets.models import (
    BookLevel,
    MarketResolution,
    OrderBookState,
    OutcomeBook,
)
from app.markets.reducer import RawMarketEvent
from app.markets.replay import ReplayMarketFeed
from app.markets.worker import MarketWorker

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TOKEN_A = "990001112223334445551"
TOKEN_B = "990001112223334445552"
MKT_1 = "mkt_worker_1"
MKT_2 = "mkt_worker_2"

FIXTURE = Path(__file__).parent / "fixtures" / "replay" / "p3_market.jsonl"


class FakeClock:
    def __init__(self) -> None:
        self.current = NOW

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def rest_book(market_id: str, *, price: str = "0.55") -> OrderBookState:
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal(price), size=Decimal("200")),),
                asks=(BookLevel(price=Decimal("0.57"), size=Decimal("150")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.43"), size=Decimal("180")),),
                asks=(BookLevel(price=Decimal("0.45"), size=Decimal("160")),),
            ),
        ),
        sequence=0,
        book_hash=f"rest_{market_id}",
        provider_timestamp=NOW,
        received_at=NOW,
    )


class FakeMarketFeed:
    """Per-market scripted streams; records subscriptions."""

    def __init__(self) -> None:
        self.queues: dict[str, asyncio.Queue] = {}
        self.subscribed: dict[str, tuple[str, ...]] = {}
        self.closed: set[str] = set()

    async def push(self, market_id: str, event: RawMarketEvent) -> None:
        queue = self.queues.get(market_id)
        if queue is not None:
            await queue.put(event)

    async def disconnect(self, market_id: str) -> None:
        queue = self.queues.get(market_id)
        if queue is not None:
            await queue.put(None)  # sentinel: stream ended

    def stream_market(self, market_id: str, asset_ids: tuple[str, ...]):
        self.subscribed[market_id] = asset_ids
        queue = self.queues.setdefault(market_id, asyncio.Queue())
        feed = self

        async def generator():
            from app.markets.live import MarketFeedDisconnected

            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        raise MarketFeedDisconnected("connection_closed")
                    yield item
            finally:
                feed.closed.add(market_id)

        return generator()


class FakeRest:
    def __init__(self) -> None:
        self.books: dict[str, OrderBookState] = {}
        self.calls: list[str] = []

    async def get_order_book(self, market_id: str) -> OrderBookState:
        self.calls.append(market_id)
        return self.books.setdefault(market_id, rest_book(market_id))

    async def get_resolution(self, market_id: str) -> MarketResolution | None:
        return None


class FakePublisher:
    def __init__(self) -> None:
        self.hot: dict[str, OrderBookState] = {}
        self.published: list[tuple[str, int]] = []
        self.gaps: list[str] = []

    async def publish_book(self, market_id: str, state: OrderBookState) -> None:
        self.hot[market_id] = state
        self.published.append((market_id, state.sequence))

    async def publish_gap(self, market_id: str, reason: str) -> None:
        self.gaps.append(reason)

    async def get_hot_book(self, market_id: str) -> OrderBookState | None:
        return self.hot.get(market_id)

    def clear_hot(self) -> None:
        self.hot.clear()


class FakeObservationSink:
    def __init__(self) -> None:
        self.batches: list[list[dict]] = []
        self.gaps: list[dict] = []

    async def save_observations(self, batch: list[dict]) -> None:
        self.batches.append(list(batch))

    async def record_tracking_gap(
        self, *, market_id: str, match_id=None, reason: str, started_at, ended_at
    ) -> None:
        self.gaps.append(
            {
                "market_id": market_id,
                "reason": reason,
                "started_at": started_at,
                "ended_at": ended_at,
            }
        )

    @property
    def total_entries(self) -> int:
        return sum(len(batch) for batch in self.batches)


class FakeRaw:
    def __init__(self) -> None:
        self.purges: list[datetime] = []

    async def purge_raw_events(self, before: datetime) -> int:
        self.purges.append(before)
        return 0


class DemandSource:
    def __init__(self, markets: set[str]) -> None:
        self.markets = markets

    async def __call__(self) -> set[str]:
        return set(self.markets)


async def token_lookup(market_id: str) -> tuple[str, str]:
    return (TOKEN_A, TOKEN_B)


def make_worker(
    clock: FakeClock,
    *,
    feed=None,
    rest=None,
    publisher=None,
    sink=None,
    raw=None,
    demand=None,
    queue_size: int = 64,
    batch_size: int = 8,
    max_subscriptions: int = 8,
    cleanup_interval_cycles: int = 50,
) -> tuple[MarketWorker, dict]:
    parts = {
        "feed": feed or FakeMarketFeed(),
        "rest": rest or FakeRest(),
        "publisher": publisher or FakePublisher(),
        "sink": sink or FakeObservationSink(),
        "raw": raw or FakeRaw(),
        "demand": demand or DemandSource({MKT_1}),
        "clock": clock,
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
        max_subscriptions=max_subscriptions,
        queue_size=queue_size,
        batch_size=batch_size,
        cleanup_interval_cycles=cleanup_interval_cycles,
    )
    return worker, parts


def book_event(market_id: str, hash_suffix: str, ts_ms: int) -> RawMarketEvent:
    return RawMarketEvent(
        event_type="book",
        asset_id=TOKEN_A,
        payload={
            "event_type": "book",
            "asset_id": TOKEN_A,
            "market": "0xconditionfake",
            "buys": [{"price": "0.51", "size": "100"}],
            "sells": [{"price": "0.58", "size": "90"}],
            "hash": f"hash_{hash_suffix}",
            "timestamp": str(ts_ms),
        },
        received_at=NOW,
    )


# ---------------------------------------------------------------------------
# Demand, subscription lifecycle and capacity
# ---------------------------------------------------------------------------


async def test_demand_drives_subscribe_and_unsubscribe():
    clock = FakeClock()
    demand = DemandSource({MKT_1})
    worker, parts = make_worker(clock, demand=demand)

    await worker.reconcile_demand_once()
    assert MKT_1 in parts["feed"].subscribed
    assert worker.subscription_state(MKT_1) == "live"
    # REST-first: the baseline came from REST before any delta.
    assert parts["rest"].calls[0] == MKT_1

    demand.markets = set()
    await worker.reconcile_demand_once()
    assert worker.subscription_state(MKT_1) == "closed"


async def test_capacity_limit_is_explicit():
    clock = FakeClock()
    demand = DemandSource({MKT_1, MKT_2})
    worker, parts = make_worker(clock, demand=demand, max_subscriptions=1)

    await worker.reconcile_demand_once()

    states = {
        MKT_1: worker.subscription_state(MKT_1),
        MKT_2: worker.subscription_state(MKT_2),
    }
    assert "capacity_limited" in states.values()
    assert "live" in states.values()


# ---------------------------------------------------------------------------
# Queueing and backpressure
# ---------------------------------------------------------------------------


async def test_receive_callback_does_no_io_and_queue_is_bounded():
    clock = FakeClock()
    worker, parts = make_worker(clock, queue_size=2)
    await worker.reconcile_demand_once()
    parts["rest"].calls.clear()

    for index in range(5):
        await parts["feed"].push(
            MKT_1, book_event(MKT_1, f"h{index}", 1_789_999_200_000 + index * 1000)
        )
    await asyncio.sleep(0.01)

    # No REST/observation I/O happened inside the receive path.
    assert parts["rest"].calls == []
    assert parts["sink"].batches == []
    assert worker.dropped_events(MKT_1) >= 3

    # Overflow marks the sub for reconcile: the next cycle REST-rebuilds the
    # baseline, drains the stale queue and records one tracking gap.
    await worker.reconcile_demand_once()
    assert parts["sink"].gaps, "overflow must record a tracking gap"

    # Fresh post-reconcile events flow into observations again.
    await parts["feed"].push(MKT_1, book_event(MKT_1, "after", 1_789_999_900_000))
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()
    assert parts["sink"].total_entries >= 1


async def test_changed_books_publish_and_batch_observations():
    clock = FakeClock()
    worker, parts = make_worker(clock, batch_size=2)
    await worker.reconcile_demand_once()
    parts["publisher"].published.clear()

    for index in range(5):
        await parts["feed"].push(
            MKT_1, book_event(MKT_1, f"b{index}", 1_789_999_200_000 + index * 1000)
        )
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()

    assert len(parts["publisher"].published) == 5
    assert parts["sink"].total_entries == 5
    assert all(len(batch) <= 2 for batch in parts["sink"].batches)
    entry = parts["sink"].batches[0][0]
    assert entry["market_id"] == MKT_1
    assert entry["kind"] == "book_change"


async def test_duplicate_hash_events_do_not_republish():
    clock = FakeClock()
    worker, parts = make_worker(clock)
    await worker.reconcile_demand_once()
    parts["publisher"].published.clear()

    same = book_event(MKT_1, "dup", 1_789_999_500_000)
    await parts["feed"].push(MKT_1, same)
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()
    first_count = len(parts["publisher"].published)

    await parts["feed"].push(MKT_1, same)
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()

    assert len(parts["publisher"].published) == first_count


# ---------------------------------------------------------------------------
# Disconnect, reconcile and hot-state loss
# ---------------------------------------------------------------------------


async def test_disconnect_triggers_rest_reconcile_and_tracking_gap():
    clock = FakeClock()
    worker, parts = make_worker(clock)
    await worker.reconcile_demand_once()
    clock.advance(30)
    parts["rest"].calls.clear()

    await parts["feed"].disconnect(MKT_1)
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()
    await asyncio.sleep(0.01)
    await worker.reconcile_demand_once()

    assert MKT_1 in parts["rest"].calls
    assert parts["sink"].gaps, "offline interval must be recorded as tracking_gap"
    gap = parts["sink"].gaps[0]
    assert gap["market_id"] == MKT_1
    assert gap["started_at"] < gap["ended_at"]
    assert worker.subscription_state(MKT_1) == "live"


async def test_redis_hot_loss_is_recovered_from_rest():
    clock = FakeClock()
    worker, parts = make_worker(clock)
    await worker.reconcile_demand_once()
    assert MKT_1 in parts["publisher"].hot

    parts["publisher"].clear_hot()
    parts["rest"].calls.clear()
    await worker.reconcile_demand_once()

    assert MKT_1 in parts["publisher"].hot
    assert MKT_1 in parts["rest"].calls


# ---------------------------------------------------------------------------
# Raw cleanup
# ---------------------------------------------------------------------------


async def test_raw_cleanup_runs_on_schedule_with_fourteen_day_cutoff():
    clock = FakeClock()
    worker, parts = make_worker(clock, cleanup_interval_cycles=2)

    await worker.reconcile_demand_once()
    assert parts["raw"].purges == []
    await worker.reconcile_demand_once()

    assert len(parts["raw"].purges) == 1
    assert parts["raw"].purges[0] == clock.now() - timedelta(days=14)


# ---------------------------------------------------------------------------
# Deterministic replay feed
# ---------------------------------------------------------------------------


async def test_replay_feed_is_deterministic_and_covers_contract_shapes():
    assert FIXTURE.is_file(), "replay fixture missing"

    async def run_once() -> list[dict]:
        clock = FakeClock()
        feed = ReplayMarketFeed(FIXTURE, now_fn=clock.now, sleep_fn=asyncio.sleep)
        worker, parts = make_worker(
            clock, feed=feed, demand=DemandSource({"mkt_replay_1"})
        )
        events: list[dict] = []
        real_publish = parts["publisher"].publish_book

        async def spy(market_id, state):
            events.append({"market_id": market_id, "hash": state.book_hash})
            await real_publish(market_id, state)

        parts["publisher"].publish_book = spy
        await worker.run_replay_once(feed)
        return events

    first = await run_once()
    second = await run_once()

    assert first == second
    assert len(first) >= 3
    assert all(entry["market_id"] == "mkt_replay_1" for entry in first)
