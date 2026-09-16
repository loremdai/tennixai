"""P3 decision worker and durable tracking demand (T65).

Orchestration contract: a canonical sports change runs prediction then
decision; a valid book change reuses the latest prediction and runs
quote/decision only; rule changes suppress actions; resolutions route to
settlement; every ledger transition commits before it is published.
Tracking demand comes from the pre-match coverage window and unresolved
paper positions — never from viewer leases.
"""

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.decision.engine import DecisionEngine, DecisionInput
from app.decision.models import DecisionAction, DecisionObservation
from app.domain import CircuitTier, Discipline, MatchStatus
from app.markets.models import MarketResolution, OrderBookState
from app.prediction.models import PredictionSnapshot


@dataclass(frozen=True)
class MatchTrackingInfo:
    status: MatchStatus
    scheduled_at: datetime | None
    circuit: CircuitTier
    discipline: Discipline


class MarketRepositoryLinks:
    """Active exact links backed by the durable market repository."""

    def __init__(self, markets) -> None:
        self._markets = markets

    async def active_links(self) -> dict[str, str]:
        rows = await self._markets.list_active_links()
        return {row.match_id: row.market_id for row in rows}

    async def market_for_match(self, match_id: str) -> str | None:
        return (await self.active_links()).get(match_id)

    async def match_for_market(self, market_id: str) -> str | None:
        for match_id, linked in (await self.active_links()).items():
            if linked == market_id:
                return match_id
        return None


COVERED_CIRCUITS = frozenset({CircuitTier.ATP, CircuitTier.WTA})


class TrackingDemand:
    def __init__(
        self,
        *,
        links,
        match_info: Callable[[str], Awaitable[MatchTrackingInfo | None]] | None,
        ledger,
        now: Callable[[], datetime],
        coverage_window: timedelta = timedelta(minutes=120),
    ) -> None:
        self._links = links
        self._match_info = match_info
        self._ledger = ledger
        self._now = now
        self._window = coverage_window

    async def demanded_markets(self) -> set[str]:
        demanded: set[str] = set(await self._ledger.unsettled_position_market_ids())
        links = await self._links.active_links()
        now = self._now()
        for match_id, market_id in links.items():
            info = (
                await self._match_info(match_id)
                if self._match_info is not None
                else None
            )
            if info is None:
                # Unknown context is tracked conservatively, never silently
                # dropped.
                demanded.add(market_id)
                continue
            if (
                info.circuit not in COVERED_CIRCUITS
                or info.discipline is not Discipline.SINGLES
            ):
                continue
            if info.status is MatchStatus.LIVE:
                demanded.add(market_id)
            elif info.scheduled_at is not None:
                delta = info.scheduled_at - now
                if timedelta(0) <= delta <= self._window:
                    demanded.add(market_id)
            elif info.status is MatchStatus.SCHEDULED:
                demanded.add(market_id)
        return demanded


class DecisionWorker:
    def __init__(
        self,
        *,
        predictor,
        engine: DecisionEngine,
        paper,
        books,
        links,
        observations,
        positions,
        publisher,
        metrics,
        clock: Callable[[], datetime],
        queue_size: int = 64,
    ) -> None:
        self._predictor = predictor
        self._engine = engine
        self._paper = paper
        self._books = books
        self._links = links
        self._observations = observations
        self._positions = positions
        self._publisher = publisher
        self._metrics = metrics
        self._clock = clock
        self._queue_size = queue_size
        self._queues: dict[str, asyncio.Queue] = {}
        self._overflow: dict[str, int] = {}
        self._latest_prediction: dict[str, PredictionSnapshot] = {}
        self._latest_book: dict[str, OrderBookState] = {}
        self._versions: dict[str, int | None] = {}

    @property
    def queue_capacity(self) -> int:
        return self._queue_size

    def backlog(self, key: str) -> int:
        queue = self._queues.get(key)
        return queue.qsize() if queue is not None else 0

    def queue_overflow_total(self) -> int:
        return sum(self._overflow.values())

    def current_version(self, match_id: str) -> int:
        return self._versions.get(match_id) or 0

    async def recover_cursors(self, match_ids) -> None:
        for match_id in match_ids:
            self._versions[
                match_id
            ] = await self._observations.latest_observation_version(match_id)

    async def _next_version(self, match_id: str) -> int:
        version = self._versions.get(match_id)
        if version is None:
            version = await self._observations.latest_observation_version(match_id)
        version += 1
        self._versions[match_id] = version
        return version

    # ------------------------------------------------------------------
    # Stream entry points
    # ------------------------------------------------------------------

    async def handle_sports(self, match_id: str, snapshot) -> None:
        started = time.perf_counter()
        prediction = await self._predictor.predict_snapshot(match_id, snapshot)
        self._metrics.observe(
            "canonical_to_prediction", (time.perf_counter() - started) * 1000
        )
        if prediction is None:
            self._metrics.increment("decision_suppressed")
            return
        self._latest_prediction[match_id] = prediction
        await self._decide(match_id, trigger="sports", started=started)

    async def handle_book(self, market_id: str, state: OrderBookState) -> None:
        started = time.perf_counter()
        match_id = await self._links.match_for_market(market_id)
        if match_id is None or match_id not in self._latest_prediction:
            # A book change never triggers a model call; without a fresh
            # prediction there is nothing to re-decide.
            return
        self._latest_book[market_id] = state
        await self._decide(match_id, trigger="book", started=started)

    async def on_resolution(self, market_id: str, resolution: MarketResolution) -> None:
        await self._paper.settle_market(market_id, resolution)

    # ------------------------------------------------------------------
    # Bounded queues with deterministic coalescing
    # ------------------------------------------------------------------

    async def submit_book(self, market_id: str, state: OrderBookState) -> None:
        queue = self._queues.setdefault(
            market_id, asyncio.Queue(maxsize=self._queue_size)
        )
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            self._overflow[market_id] = self._overflow.get(market_id, 0) + 1
            self._metrics.increment("queue_overflow")
        queue.put_nowait(state)

    async def pump_once(self, market_id: str) -> None:
        queue = self._queues.get(market_id)
        if queue is None:
            return
        newest = None
        while not queue.empty():
            newest = queue.get_nowait()
        if newest is not None:
            await self.handle_book(market_id, newest)

    # ------------------------------------------------------------------
    # Decision cycle
    # ------------------------------------------------------------------

    async def _decide(self, match_id: str, *, trigger: str, started: float) -> None:
        prediction = self._latest_prediction.get(match_id)
        if prediction is None:
            return
        market_id = await self._links.market_for_match(match_id)
        book = None
        metadata = None
        rules_current = None
        if market_id is not None:
            book = self._latest_book.get(market_id) or await self._books.get_book(
                market_id
            )
            metadata = await self._books.get_metadata(market_id)
            rules_current = await self._books.get_rules_hash(market_id)
        rules_frozen = await self._books.get_frozen_rules_hash(match_id)
        position = await self._positions.get_position(match_id)

        version = await self._next_version(match_id)
        data = DecisionInput(
            match_id=match_id,
            market_id=market_id,
            mapped=market_id is not None,
            observation_version=version,
            as_of=self._clock(),
            prediction=prediction,
            book=book,
            metadata=metadata,
            rules_current_hash=rules_current,
            rules_frozen_hash=rules_frozen,
            position=position,
            is_stale=bool(book is not None and book.is_stale),
        )
        observation: DecisionObservation = self._engine.evaluate(data)

        # Commit decision evidence, then the ledger transition, then publish.
        await self._observations.save_decision_observation(observation)
        if observation.action in (DecisionAction.BUY, DecisionAction.SELL):
            await self._paper.on_decision(
                observation,
                book=book,
                metadata=metadata,
                rules_hash=rules_current,
            )
            self._metrics.observe(
                "ledger_commit_to_publish", (time.perf_counter() - started) * 1000
            )
        await self._publisher.publish_decision(observation)

        elapsed_ms = (time.perf_counter() - started) * 1000
        if trigger == "sports":
            self._metrics.observe("prediction_to_decision", elapsed_ms)
            self._metrics.observe("sports_to_decision", elapsed_ms)
        else:
            self._metrics.observe("book_to_decision", elapsed_ms)
