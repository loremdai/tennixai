"""Local runtime daemon (T78).

The daemon is the single sequential owner of the local real runtime: it
reconciles durable demand, pumps coalesced decision queues, executes due
paper intents against the canonical hot book, and runs bounded discovery
jobs at the exact default intervals (live catalog 60s, upcoming catalog
600s, rankings 86,400s, market discovery and resolution/rules recheck
120s). Job failures degrade health without crashing the loop or deleting
prior canonical data; strict mapping is the only path to a link; provider
resolutions route solely through ``DecisionWorker.on_resolution``; recovery
writes an explicit gap before restoring subscriptions and cursors; and
shutdown flushes buffered work and persists final health.

Discipline: paper-only forever (no wallet, keys, signing or orders), no LLM
call in any up-path, no provider identifier/URL/secret in health payloads
or logs, and no reset/truncate/volume deletion anywhere.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domain import MatchStatus
from app.errors import AppError
from app.markets.mapping import (
    LinkDecision,
    MappingStatus,
    evaluate_link_change,
    map_market,
)
from app.markets.models import MarketListingScan, MarketStatus, ResolutionStatus
from app.markets.quotes import realtime_quote_record
from app.persistence.market_repositories import LinkFrozenError
from app.runtime.health import (
    MARKET_SOURCE,
    RECOVERY_REASON,
    SPORTS_SOURCE,
    RuntimeHealthRegistry,
    stable_reason_code,
)

__all__ = [
    "BoundedJobScheduler",
    "LocalRuntimeDaemon",
    "MarketBridge",
    "RuntimeJob",
    "SportsBridge",
    "TrackingDemandSource",
    "TtlCache",
    "stable_reason_code",
]

DECISION_SOURCE = "decision"
PAPER_SOURCE = "paper_execution"
RECOVERY_SOURCE = "recovery"
TICK_SOURCE = "daemon_tick"


class RuntimeJobError(Exception):
    """Internal job failure carrying a sanitized stable reason code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TtlCache:
    """TTL cache over a single-argument async loader.

    Used for the per-decision provider reads (execution metadata, rules) that
    would otherwise fire several fresh REST calls on every ~1s tick. One
    instance can be shared across call sites — the daemon's paper path and the
    decision book source share a single metadata cache — so the runtime issues
    at most one refresh per key per TTL window. A failed load raises unchanged
    (the callers' typed failure semantics apply) and never poisons the cache:
    errors are not cached and an entry is never served once its TTL has passed.
    """

    def __init__(
        self,
        loader: Callable[[str], Awaitable[Any]],
        clock: Callable[[], datetime],
        *,
        ttl: timedelta,
    ) -> None:
        self._loader = loader
        self._clock = clock
        self._ttl = ttl
        self._entries: dict[str, tuple[datetime, Any]] = {}

    async def get(self, key: str) -> Any:
        now = self._clock()
        cached = self._entries.get(key)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]
        value = await self._loader(key)
        self._entries[key] = (now, value)
        return value


# ---------------------------------------------------------------------------
# Bounded scheduling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeJob:
    name: str
    interval: timedelta
    run: Callable[[], Awaitable[None]]


class BoundedJobScheduler:
    """Runs each job at most once per interval; failures degrade health.

    The last-run stamp is set BEFORE the job runs so a slow or failing job
    can never tighten its own interval, and a failure never deletes prior
    canonical data — it only marks the job's health source degraded.
    """

    def __init__(
        self, *, jobs: list[RuntimeJob], health: RuntimeHealthRegistry
    ) -> None:
        self._jobs = jobs
        self._health = health
        self._last_run: dict[str, datetime] = {}

    async def run_due(self, now: datetime) -> None:
        for job in self._jobs:
            last = self._last_run.get(job.name)
            if last is not None and now - last < job.interval:
                continue
            self._last_run[job.name] = now
            try:
                await job.run()
            except Exception as exc:  # noqa: BLE001 - contained by design
                await self._health.mark_degraded(job.name, stable_reason_code(exc))
            else:
                await self._health.mark_success(job.name)


# ---------------------------------------------------------------------------
# Worker bridges: health + decision wiring
# ---------------------------------------------------------------------------


class SportsBridge:
    """RealtimeWorker hooks → health registry + DecisionWorker."""

    def __init__(
        self,
        *,
        decision_worker: Any,
        health: RuntimeHealthRegistry,
        source: str = SPORTS_SOURCE,
    ) -> None:
        self._decision_worker = decision_worker
        self._health = health
        self._source = source

    async def on_snapshot(self, match_id: str, snapshot: Any) -> None:
        # A confirmed canonical event proves the connection is alive; quiet
        # scorelines never mark a healthy websocket stale.
        await self._health.mark_success(self._source)
        await self._decision_worker.handle_sports(match_id, snapshot)

    async def on_connection(self, match_id: str, state: str) -> None:
        await _apply_connection(self._health, self._source, state)


class MarketBridge:
    """MarketWorker hooks → health registry + DecisionWorker.

    Book consumption is idempotent: an unchanged baseline (identical
    book_hash) is never re-decided, only counted as a duplicate.
    """

    def __init__(
        self,
        *,
        decision_worker: Any,
        health: RuntimeHealthRegistry,
        source: str = MARKET_SOURCE,
    ) -> None:
        self._decision_worker = decision_worker
        self._health = health
        self._source = source
        self._last_hash: dict[str, str] = {}
        self.duplicates = 0

    async def on_state(self, market_id: str, state: Any) -> None:
        book_hash = getattr(state, "book_hash", None)
        if book_hash is not None:
            if self._last_hash.get(market_id) == book_hash:
                self.duplicates += 1
                return
            self._last_hash[market_id] = book_hash
        await self._health.mark_success(self._source)
        await self._decision_worker.submit_book(market_id, state)

    async def on_connection(self, market_id: str, state: str) -> None:
        await _apply_connection(self._health, self._source, state)


async def _apply_connection(
    health: RuntimeHealthRegistry, source: str, state: str
) -> None:
    if state == "live":
        await health.mark_success(source)
    else:
        # Disconnect/reconnect windows are gaps: new BUY/SELL stay revoked
        # until REST reconciliation succeeds and reports "live" again.
        await health.mark_gap(source, "CONNECTION_LOST")


class TrackingDemandSource:
    """P3-tracking-only demand for the realtime viewer cycle.

    Per-source isolation: a tracking/links DB failure degrades health and
    falls back to the last known demand — it never aborts the cycle and
    never fabricates new subscriptions.
    """

    def __init__(
        self,
        *,
        tracking: Any,
        links: Any,
        health: RuntimeHealthRegistry,
        source: str = "p3_tracking",
    ) -> None:
        self._tracking = tracking
        self._links = links
        self._health = health
        self._source = source
        self._last_known: dict[str, str] = {}

    async def __call__(self) -> dict[str, str]:
        try:
            tracked = await self._tracking.demanded_markets()
            links = await self._links.active_links()
        except Exception as exc:  # noqa: BLE001 - isolated by design
            await self._health.mark_degraded(self._source, stable_reason_code(exc))
            return dict(self._last_known)
        demand = {
            match_id: "active"
            for match_id, market_id in links.items()
            if market_id in tracked
        }
        self._last_known = demand
        return demand


# ---------------------------------------------------------------------------
# The daemon
# ---------------------------------------------------------------------------


class LocalRuntimeDaemon:
    def __init__(
        self,
        *,
        realtime: Any,
        market_worker: Any,
        decision_worker: Any,
        health: RuntimeHealthRegistry,
        clock: Callable[[], datetime],
        paper: Any,
        hot_books: Any,
        market_provider: Any,
        markets: Any,
        ledger: Any,
        catalog_provider: Any,
        catalog_store: Any,
        directory: Any,
        resolver: Any,
        metrics: Any = None,
        metadata_cache: TtlCache | None = None,
        quote_job: Any = None,
        quote_snapshots: Any = None,
        catalog_quote_feed: Any = None,
        quote_change_notifier: Callable[..., Awaitable[Any]] | None = None,
        quote_fresh_seconds: int = 300,
        market_snapshot_seconds: int = 120,
        tick_seconds: float = 1.0,
        live_catalog_seconds: int = 60,
        upcoming_catalog_seconds: int = 600,
        ranking_seconds: int = 86_400,
        market_discovery_seconds: int = 120,
        max_resolution_targets: int = 32,
        closed_market_window: timedelta = timedelta(hours=24),
    ) -> None:
        self._realtime = realtime
        self._market_worker = market_worker
        self._decision_worker = decision_worker
        self._health = health
        self._clock = clock
        self._paper = paper
        self._hot_books = hot_books
        self._market_provider = market_provider
        self._markets = markets
        self._ledger = ledger
        self._catalog_provider = catalog_provider
        self._catalog_store = catalog_store
        self._directory = directory
        self._resolver = resolver
        self._metrics = metrics
        self._quote_job = quote_job
        self._quote_snapshots = quote_snapshots
        self._catalog_quote_feed = catalog_quote_feed
        self._quote_change_notifier = quote_change_notifier
        self._catalog_quote_task: asyncio.Task | None = None
        self._quote_fresh_seconds = quote_fresh_seconds
        self._mirrored_hashes: dict[str, str] = {}
        self._tick_seconds = tick_seconds
        self._max_resolution_targets = max_resolution_targets
        self._closed_window = closed_market_window

        self._recently_closed: dict[str, datetime] = {}
        # Shared with the decision book source when the assembly injects one
        # cache for both paths; the TTL matches the discovery cadence.
        self._metadata_cache = metadata_cache or TtlCache(
            market_provider.get_execution_metadata,
            clock,
            ttl=timedelta(seconds=market_discovery_seconds),
        )
        self._alias_synced: set[str] = set()
        # Per-class rotation cursors for the bounded resolution recheck plus
        # the number of unique targets skipped in the most recent cycle.
        self._resolution_offsets: dict[str, int] = {}
        self._resolution_skipped = 0
        self._recovered = False
        self._stopping = False

        # The resolution/rules recheck never runs more often than discovery.
        self._jobs = BoundedJobScheduler(
            health=health,
            jobs=[
                RuntimeJob(
                    "live_catalog",
                    timedelta(seconds=live_catalog_seconds),
                    self._sync_live_catalog,
                ),
                RuntimeJob(
                    "upcoming_catalog",
                    timedelta(seconds=upcoming_catalog_seconds),
                    self._sync_upcoming_catalog,
                ),
                RuntimeJob(
                    "rankings", timedelta(seconds=ranking_seconds), self._sync_rankings
                ),
                RuntimeJob(
                    "market_discovery",
                    timedelta(seconds=market_discovery_seconds),
                    self._discover_markets,
                ),
                RuntimeJob(
                    "resolution_recheck",
                    timedelta(seconds=market_discovery_seconds),
                    self._resolution_recheck,
                ),
                RuntimeJob(
                    "market_snapshot",
                    timedelta(seconds=market_snapshot_seconds),
                    self._run_market_snapshot,
                ),
            ],
        )
        # One health surface: pipeline counters flow into every persist().
        health.attach_counters(self._collect_counters)

    @property
    def recovered(self) -> bool:
        return self._recovered

    # ------------------------------------------------------------------
    # Loop lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._stopping = False
        try:
            while not self._stopping:
                try:
                    if not self._recovered:
                        await self.recover_once()
                    await self.tick_once()
                except Exception as exc:  # noqa: BLE001 - the loop must survive
                    await self._health.mark_degraded(
                        TICK_SOURCE, stable_reason_code(exc)
                    )
                    # A failing state persist never kills the loop; cancellation
                    # still propagates.
                    with contextlib.suppress(Exception):
                        await self._health.persist()
                else:
                    await self._health.mark_success(TICK_SOURCE)
                if (
                    not self._stopping
                    and self._catalog_quote_feed is not None
                    and self._catalog_quote_task is None
                ):
                    self._catalog_quote_task = asyncio.create_task(
                        self._catalog_quote_feed.run(),
                        name="market-catalog-quote-feed",
                    )
                await asyncio.sleep(self._tick_seconds)
        finally:
            await self._stop_catalog_quote_feed()

    async def stop(self) -> None:
        """Graceful shutdown: no new demand, sockets closed, buffered
        observations flushed by the workers, final health persisted.
        Nothing is deleted."""
        self._stopping = True
        await self._stop_catalog_quote_feed()
        with contextlib.suppress(Exception):
            await self._realtime.stop()
        with contextlib.suppress(Exception):
            await self._market_worker.stop()
        # Shutdown must complete even when the final persist cannot reach
        # the state store; workers are stopped either way and nothing is
        # deleted.
        with contextlib.suppress(Exception):
            await self._health.persist()

    async def _stop_catalog_quote_feed(self) -> None:
        task, self._catalog_quote_task = self._catalog_quote_task, None
        if task is None:
            return
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    async def tick_once(self) -> None:
        await self._realtime.reconcile_demand_once()
        await self._market_worker.reconcile_demand_once()
        await self._pump_markets()
        await self._jobs.run_due(self._clock())
        await self._health.persist()

    async def _pump_markets(self) -> None:
        """Pump every active market with strict per-market isolation.

        One market's transient failure (a provider 5xx, a book-source error)
        degrades only that market's contribution to the `decision` health
        source: the failing market's own decision pump and paper intake
        (`_execute_due_intents`) are skipped for that tick, while every
        remaining market's pump and paper execution plus the bounded jobs
        still run in the same tick. `asyncio.CancelledError` is a
        `BaseException`, so `except Exception` never swallows cancellation —
        it propagates to `run()` and stops the loop as before. Degradation is
        reported once per tick with the first stable reason code, mirroring
        the bounded-job scheduler's aggregate semantics: a clean market later
        in the loop must not overwrite an earlier market's failure.
        """
        failures: list[str] = []
        pumped = False
        for market_id in self._market_worker.active_market_ids():
            pumped = True
            try:
                await self._decision_worker.pump_once(market_id)
                await self._execute_due_intents(market_id)
                await self._mirror_hot_book(market_id)
            except Exception as exc:  # noqa: BLE001 - per-market isolation
                failures.append(stable_reason_code(exc))
        if failures:
            await self._health.mark_degraded(DECISION_SOURCE, failures[0])
        elif pumped:
            await self._health.mark_success(DECISION_SOURCE)

    async def recover_once(self) -> None:
        """Rebuild from durable state only (PostgreSQL): explicit gap first,
        then cursors, subscriptions and hot books via REST reconciliation."""
        await self._health.mark_gap(SPORTS_SOURCE, RECOVERY_REASON)
        await self._health.mark_gap(MARKET_SOURCE, RECOVERY_REASON)
        # The gap is recorded in memory first; a persist failure must never
        # abort recovery or escape into the run loop — the next successful
        # persist writes the same truthful state.
        with contextlib.suppress(Exception):
            await self._health.persist()
        try:
            rows = await self._markets.list_active_links()
            await self._decision_worker.recover_cursors({row.match_id for row in rows})
            await self._realtime.reconcile_demand_once()
            await self._market_worker.reconcile_demand_once()
        except Exception as exc:  # noqa: BLE001 - retry on the next loop pass
            # The gap stays: new BUY/SELL remain revoked until reconciliation
            # actually succeeds. Health is persisted so `status` is truthful.
            await self._health.mark_degraded(RECOVERY_SOURCE, stable_reason_code(exc))
            with contextlib.suppress(Exception):
                await self._health.persist()
            return
        await self._health.mark_recovered(SPORTS_SOURCE)
        await self._health.mark_recovered(
            MARKET_SOURCE, tracked=len(self._market_worker.active_market_ids())
        )
        with contextlib.suppress(Exception):
            await self._health.persist()
        self._recovered = True

    # ------------------------------------------------------------------
    # Paper maintenance
    # ------------------------------------------------------------------

    async def _execute_due_intents(self, market_id: str) -> None:
        degraded = False
        book = None
        try:
            book = await self._hot_books.get_hot_book(market_id)
        except Exception as exc:  # noqa: BLE001 - fail closed to None
            degraded = True
            await self._health.mark_degraded(PAPER_SOURCE, stable_reason_code(exc))
        metadata = None
        if book is not None:
            # Fetch ONLY the canonical hot book plus execution metadata for
            # this market; anything else is out of the up-path.
            try:
                metadata = await self._execution_metadata(market_id)
            except Exception as exc:  # noqa: BLE001 - fail closed to None
                degraded = True
                await self._health.mark_degraded(PAPER_SOURCE, stable_reason_code(exc))
        # None lets the existing BOOK_UNVERIFIABLE/NO_FILL semantics apply;
        # a fill is never manufactured from missing or failed reconciliation.
        await self._paper.execute_due_intents(
            book=book, metadata=metadata, market_id=market_id
        )
        if not degraded and book is not None:
            await self._health.mark_success(PAPER_SOURCE)

    async def _execution_metadata(self, market_id: str) -> Any:
        # Delegates to the shared TTL cache. A failed load raises and is never
        # served from a stale cache nor cached as an error.
        return await self._metadata_cache.get(market_id)

    # ------------------------------------------------------------------
    # Coverage lane
    # ------------------------------------------------------------------

    async def _run_market_snapshot(self) -> None:
        """Run one bounded coverage round and publish its coverage facts.

        The lane writes display quotes only: no prediction, no decision, no
        paper, no WebSocket. A failed round keeps the previous coverage and
        the previous projection rows (the scheduler marks the job degraded).
        """
        if self._quote_job is None:
            return
        coverage = await self._quote_job.run_once()
        self._health.set_market_coverage(coverage)
        if coverage.batch_failures:
            raise RuntimeJobError("MARKET_SNAPSHOT_BATCH_FAILED")
        if coverage.rate_limited:
            raise RuntimeJobError("MARKET_SNAPSHOT_RATE_LIMITED")

    async def _mirror_hot_book(self, market_id: str) -> None:
        """Mirror the realtime hot book into the shared projection so pages
        read one precedence rule for both lanes. A missing book writes
        nothing; a store failure degrades the market source without
        suppressing the just-published decision book."""
        if self._quote_snapshots is None:
            return
        try:
            book = await self._hot_books.get_hot_book(market_id)
        except Exception as exc:  # noqa: BLE001 - isolate the mirror
            await self._health.mark_degraded(MARKET_SOURCE, stable_reason_code(exc))
            return
        if book is None:
            return
        if self._mirrored_hashes.get(market_id) == book.book_hash:
            # The decision loop must not pay a store round-trip per market per
            # tick: only a real book change touches the projection.
            return
        try:
            await self._quote_snapshots.upsert(
                realtime_quote_record(book, fresh_seconds=self._quote_fresh_seconds)
            )
        except Exception as exc:  # noqa: BLE001 - isolate the mirror
            await self._health.mark_degraded(MARKET_SOURCE, stable_reason_code(exc))
            return
        self._mirrored_hashes[market_id] = book.book_hash

    # ------------------------------------------------------------------
    # Bounded discovery jobs
    # ------------------------------------------------------------------

    async def _sync_live_catalog(self) -> None:
        matches = await self._catalog_provider.get_live_matches()
        await self._store_matches(matches)

    async def _sync_upcoming_catalog(self) -> None:
        matches = await self._catalog_provider.get_fixtures()
        await self._store_matches(matches)

    async def _store_matches(self, matches: list[Any]) -> None:
        newly = await self._catalog_store.upsert_matches(
            matches, observed_at=self._clock()
        )
        new_ids = set(newly) - self._alias_synced
        if new_ids:
            await self._directory.sync_player_aliases(sorted(new_ids))
            self._alias_synced |= new_ids

    async def _sync_rankings(self) -> None:
        report = await self._directory.sync_rankings()
        if report.failed:
            raise RuntimeJobError("RANKINGS_SYNC_FAILED")

    async def _discover_markets(self) -> None:
        scan: MarketListingScan = (
            await self._market_provider.list_tennis_market_listings()
        )
        now = self._clock()
        changed = await self._markets.reconcile_market_listings(scan, observed_at=now)
        if changed and self._quote_change_notifier is not None:
            await self._quote_change_notifier(count=changed)
        candidates = [
            *await self._catalog_store.list_matches(MatchStatus.LIVE),
            *await self._catalog_store.list_matches(MatchStatus.SCHEDULED),
        ]
        current_by_match = {
            row.match_id: row.market_id
            for row in await self._markets.list_active_links()
        }
        failures: list[str] = []
        for listing in scan.listings:
            market = listing.to_market()
            if market is None:
                continue
            try:
                if market.status is MarketStatus.CLOSED:
                    self._recently_closed[market.id] = now
                mapped = await self._link_if_strict_match(
                    market, candidates, current_by_match
                )
                if mapped:
                    await self._capture_rules(market.id)
            except Exception as exc:  # noqa: BLE001 - one bad market never
                failures.append(stable_reason_code(exc))  # aborts the batch
        if failures:
            raise RuntimeJobError(failures[0])

    async def _capture_rules(self, market_id: str) -> None:
        try:
            rules = await self._market_provider.get_rules(market_id)
        except AppError as exc:
            if exc.code == "not_found":
                # Rules are optional upstream; the market stays visible.
                return
            raise
        await self._markets.save_rules(rules)

    async def _link_if_strict_match(
        self, market: Any, candidates: list[Any], current_by_match: dict[str, str]
    ) -> bool:
        result = await map_market(market, candidates, self._resolver)
        if result.status is not MappingStatus.MAPPED or result.match_id is None:
            # A failed mapping stays MARKET_ONLY: no fuzzy, LLM or manual
            # fallback ever creates a link.
            return False
        intent_exists = (
            await self._ledger.count_intents_for_match(result.match_id)
        ) > 0
        decision = evaluate_link_change(
            current_market_id=current_by_match.get(result.match_id),
            target_market_id=market.id,
            intent_exists=intent_exists,
        )
        if decision not in (LinkDecision.CREATE, LinkDecision.REPLACE):
            return True
        evidence = {
            "player_ids": list(result.player_ids or ()),
            "candidate_count": result.candidate_count,
            "method": "strict_pair_mapping",
        }
        try:
            await self._markets.link_match(
                market_id=market.id, match_id=result.match_id, evidence=evidence
            )
        except LinkFrozenError:
            # Frozen links are authoritative; discovery never rewrites them.
            return True
        current_by_match[result.match_id] = market.id
        return True

    async def _resolution_recheck(self) -> None:
        now = self._clock()
        cutoff = now - self._closed_window
        self._recently_closed = {
            market_id: closed_at
            for market_id, closed_at in self._recently_closed.items()
            if closed_at >= cutoff
        }
        active = {row.market_id for row in await self._markets.list_active_links()}
        unsettled = set(await self._ledger.unsettled_position_market_ids())
        targets = self._select_resolution_targets(
            unsettled=unsettled,
            closed=set(self._recently_closed),
            active=active,
        )
        failures: list[str] = []
        for market_id in targets:
            try:
                resolution = await self._market_provider.get_resolution(market_id)
            except Exception as exc:  # noqa: BLE001 - keep the batch bounded
                failures.append(stable_reason_code(exc))
                continue
            if resolution is not None and (resolution.status is ResolutionStatus.FINAL):
                # Provider final resolutions route ONLY through the decision
                # worker's settlement path.
                await self._decision_worker.on_resolution(market_id, resolution)
            # Rules maintenance is best-effort re-refresh; a rules fetch
            # failure never blocks resolution routing nor aborts the batch.
            with contextlib.suppress(Exception):
                await self._capture_rules(market_id)
        if failures:
            raise RuntimeJobError(failures[0])

    def _select_resolution_targets(
        self, *, unsettled: set[str], closed: set[str], active: set[str]
    ) -> list[str]:
        """Priority-ordered, bounded and rotating resolution targets.

        Unsettled positions outrank recently closed markets, which outrank
        active links; each class is deduplicated against the higher-priority
        classes and internally stable-ordered (sorted). While the union fits
        under the cap the selection is unchanged; once a class overflows the
        remaining budget it rotates through a per-class cursor so every
        target is eventually rechecked — deterministic for the same input
        sets and call count. Only the aggregate skipped count is exposed;
        market identifiers never enter health payloads.
        """
        budget = self._max_resolution_targets
        selected: list[str] = []
        seen: set[str] = set()
        for key, members in (
            ("unsettled", unsettled),
            ("closed", closed),
            ("active", active),
        ):
            ordered = sorted(members - seen)
            if not ordered:
                continue
            seen.update(ordered)
            if len(ordered) > budget:
                offset = self._resolution_offsets.get(key, 0) % len(ordered)
                rolled = ordered[offset:] + ordered[:offset]
                picked = rolled[:budget]
                self._resolution_offsets[key] = (offset + budget) % len(ordered)
            else:
                picked = ordered
            selected.extend(picked)
            budget -= len(picked)
        self._resolution_skipped = len(seen) - len(selected)
        return selected

    # ------------------------------------------------------------------
    # Health surface unification
    # ------------------------------------------------------------------

    def _collect_counters(self) -> dict[str, int]:
        counters: dict[str, int] = {}
        if self._metrics is not None:
            with contextlib.suppress(Exception):
                exported = json.loads(self._metrics.export())
                counters.update(
                    {
                        str(key): int(value)
                        for key, value in exported.get("counters", {}).items()
                    }
                )
        counters["realtime_callback_failures"] = sum(
            getattr(self._realtime, "callback_failures", {}).values()
        )
        counters["market_callback_failures"] = sum(
            getattr(self._market_worker, "callback_failures", {}).values()
        )
        overflow = getattr(self._decision_worker, "queue_overflow_total", None)
        counters["decision_queue_overflow"] = (
            int(overflow()) if callable(overflow) else 0
        )
        # Truthful overflow visibility for the bounded resolution recheck:
        # how many unique targets the cap skipped in the most recent cycle.
        counters["resolution_targets_skipped"] = self._resolution_skipped
        return counters
