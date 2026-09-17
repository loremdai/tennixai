"""Local runtime daemon tests (T78).

The daemon is the single sequential owner of the runtime loops: it
reconciles demand, pumps coalesced decision queues, executes due paper
intents against the canonical hot book, and runs bounded discovery jobs at
the exact default intervals (live catalog 60s, upcoming catalog 600s,
rankings 86,400s, market discovery / resolution recheck 120s). Job failures
degrade health without crashing the loop or deleting prior canonical data;
strict mapping is the only path to a link; resolutions route solely through
`DecisionWorker.on_resolution`; recovery writes an explicit gap before
restoring subscriptions and cursors; and shutdown flushes and persists.
All deterministic via fake clock — no provider, LLM, or network access.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta

import pytest
from p3_fakes import make_book, make_resolution, make_rules
from tests_support import FakeClock, build_service_inputs

from app.decision.worker import MarketRepositoryLinks
from app.domain import (
    DataFreshness,
    Discipline,
    Gender,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.markets.models import Market, MarketOutcome, MarketStatus, ResolutionStatus
from app.persistence.market_repositories import LinkFrozenError
from app.players.models import PlayerResolution, PlayerResolutionStatus
from app.players.sync import DirectorySyncReport
from app.realtime.p3_metrics import P3Metrics
from app.runtime.daemon import (
    LocalRuntimeDaemon,
    MarketBridge,
    SportsBridge,
    TrackingDemandSource,
    stable_reason_code,
)
from app.runtime.health import (
    MARKET_SOURCE,
    RECOVERY_REASON,
    SPORTS_SOURCE,
    RuntimeHealthRegistry,
)
from app.runtime.models import RuntimeSourceStatus

INPUTS = build_service_inputs()
NOW = FakeClock().now()


# ---------------------------------------------------------------------------
# Domain factories
# ---------------------------------------------------------------------------


def make_match(
    match_id: str = "mat_1",
    *,
    status: MatchStatus = MatchStatus.SCHEDULED,
    player_a: str = "ply_a",
    player_b: str = "ply_b",
) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=(
            Player(id=player_a, name="Player One"),
            Player(id=player_b, name="Player Two"),
        ),
        tournament=Tournament(
            id="trn_1",
            name="Test Open",
            tour="atp",
            discipline=Discipline.SINGLES,
            gender=Gender.MEN,
        ),
        scheduled_at=NOW,
        freshness=DataFreshness(provider="test", observed_at=NOW),
    )


def make_provider_market(
    market_id: str,
    *,
    status: MarketStatus = MarketStatus.OPEN,
    player_a: str = "ply_a",
    player_b: str = "ply_b",
    name_a: str = "Player One",
    name_b: str = "Player Two",
) -> Market:
    return Market(
        id=market_id,
        question=f"{name_a} vs. {name_b}: Match Winner",
        outcomes=(
            MarketOutcome(player_id=player_a, name=name_a),
            MarketOutcome(player_id=player_b, name=name_b),
        ),
        status=status,
        rules_version=1,
        event_start=NOW,
        event_end=NOW + timedelta(hours=3),
        provider="polymarket",
        observed_at=NOW,
    )


def make_player(player_id: str, name: str) -> Player:
    return Player(id=player_id, name=name)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class LinkRow:
    market_id: str
    match_id: str


class FakeCatalogProvider:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.live_matches: list[Match] = []
        self.fixtures: list[Match] = []
        self.live_calls = 0
        self.fixture_calls = 0
        self.raise_on_live: Exception | None = None

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        self.log.append("job:live_catalog")
        self.live_calls += 1
        if self.raise_on_live is not None:
            raise self.raise_on_live
        return list(self.live_matches)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        self.log.append("job:upcoming_catalog")
        self.fixture_calls += 1
        return list(self.fixtures)


class FakeCatalogStore:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.rows: dict[str, Match] = {}
        self.upsert_calls: list[tuple[tuple[str, ...], object]] = []
        self.newly_seen: set[str] = set()

    async def upsert_matches(self, matches, *, observed_at) -> set[str]:
        ids = tuple(match.id for match in matches)
        self.upsert_calls.append((ids, observed_at))
        for match in matches:
            self.rows[match.id] = match
        return set(self.newly_seen)

    async def get_match(self, match_id: str) -> Match | None:
        return self.rows.get(match_id)

    async def list_matches(
        self, status: MatchStatus, *, player_id: str | None = None
    ) -> list[Match]:
        return [match for match in self.rows.values() if match.status is status]


class FakeDirectory:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.rankings_calls = 0
        self.alias_calls: list[tuple[str, ...]] = []
        self.report = DirectorySyncReport()
        self.raise_on_rankings: Exception | None = None

    async def sync_rankings(self) -> DirectorySyncReport:
        self.log.append("job:rankings")
        self.rankings_calls += 1
        if self.raise_on_rankings is not None:
            raise self.raise_on_rankings
        return self.report

    async def sync_player_aliases(self, player_ids) -> DirectorySyncReport:
        self.alias_calls.append(tuple(sorted(player_ids)))
        return DirectorySyncReport()


class FakeMarketProvider:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.markets: list[Market] = []
        self.rules: dict[str, object] = {}
        self.rules_missing: set[str] = set()
        self.resolutions: dict[str, object] = {}
        self.metadata: dict[str, object] = {}
        self.metadata_raises: Exception | None = None
        self.discovery_calls = 0
        self.rules_calls: list[str] = []
        self.resolution_calls: list[str] = []
        self.metadata_calls: list[str] = []

    async def list_tennis_moneylines(self) -> tuple[Market, ...]:
        self.log.append("job:market_discovery")
        self.discovery_calls += 1
        return tuple(self.markets)

    async def get_rules(self, market_id: str):
        self.rules_calls.append(market_id)
        if market_id in self.rules_missing:
            raise AppError("not_found", "rules unavailable", 404)
        return self.rules[market_id]

    async def get_resolution(self, market_id: str):
        self.resolution_calls.append(market_id)
        return self.resolutions.get(market_id)

    async def get_execution_metadata(self, market_id: str):
        self.metadata_calls.append(market_id)
        if self.metadata_raises is not None:
            raise self.metadata_raises
        return self.metadata[market_id]


class FakeMarketsRepo:
    def __init__(self) -> None:
        self.saved_markets: list[str] = []
        self.saved_rules: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.link_evidence: list[dict] = []
        self.active_links_rows: list[LinkRow] = []
        self.frozen: set[str] = set()

    async def save_market(self, market: Market) -> None:
        self.saved_markets.append(market.id)

    async def save_rules(self, rules) -> int:
        self.saved_rules.append(rules.market_id)
        return 1

    async def list_active_links(self) -> list[LinkRow]:
        return list(self.active_links_rows)

    async def link_match(
        self, *, market_id: str, match_id: str, evidence: dict
    ) -> None:
        if market_id in self.frozen:
            raise LinkFrozenError(market_id)
        self.links.append((market_id, match_id))
        self.link_evidence.append(evidence)


class FakeLedger:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.intents: dict[str, int] = {}
        self.unsettled: set[str] = set()
        self.unsettled_calls = 0

    async def count_intents_for_match(self, match_id: str) -> int:
        return self.intents.get(match_id, 0)

    async def unsettled_position_market_ids(self) -> tuple[str, ...]:
        self.log.append("job:resolution_recheck")
        self.unsettled_calls += 1
        return tuple(sorted(self.unsettled))


class FakeLinkRepo:
    def __init__(self, rows: list[LinkRow]) -> None:
        self.rows = rows

    async def list_active_links(self) -> list[LinkRow]:
        return list(self.rows)


class FakeResolver:
    def __init__(self, players: dict[str, Player]) -> None:
        self._players = players

    async def resolve(self, query: str, *, context_player_ids=(), limit: int = 5):
        player = self._players.get(query)
        if player is None:
            return PlayerResolution(
                status=PlayerResolutionStatus.NOT_FOUND, query=query
            )
        return PlayerResolution(
            status=PlayerResolutionStatus.RESOLVED, query=query, player=player
        )


class RecordingDecisionWorker:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.pump_calls: list[str] = []
        self.submitted: list[tuple[str, object]] = []
        self.sports: list[tuple[str, object]] = []
        self.resolutions: list[tuple[str, object]] = []
        self.recovered: list[frozenset[str]] = []
        self.overflow = 0

    async def pump_once(self, market_id: str) -> None:
        self.log.append(f"pump:{market_id}")
        self.pump_calls.append(market_id)

    async def submit_book(self, market_id: str, state) -> None:
        self.submitted.append((market_id, state))

    async def handle_sports(self, match_id: str, snapshot) -> None:
        self.sports.append((match_id, snapshot))

    async def on_resolution(self, market_id: str, resolution) -> None:
        self.resolutions.append((market_id, resolution))

    async def recover_cursors(self, match_ids) -> None:
        self.recovered.append(frozenset(match_ids))

    def queue_overflow_total(self) -> int:
        return self.overflow


class RecordingPaper:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls: list[tuple[str, bool, bool]] = []

    async def execute_due_intents(self, *, book, metadata, market_id=None) -> None:
        self.log.append(f"intents:{market_id}")
        self.calls.append((market_id, book is not None, metadata is not None))


class FakeHotBooks:
    def __init__(self) -> None:
        self.books: dict[str, object] = {}
        self.raise_error: Exception | None = None

    async def get_hot_book(self, market_id: str):
        if self.raise_error is not None:
            raise self.raise_error
        return self.books.get(market_id)


class FakeRealtime:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.reconcile_calls = 0
        self.stopped = False
        self.reconcile_raises: Exception | None = None
        self.callback_failures = {"on_snapshot": 0, "on_connection": 0}

    async def reconcile_demand_once(self) -> None:
        self.log.append("realtime.reconcile")
        self.reconcile_calls += 1
        if self.reconcile_raises is not None:
            raise self.reconcile_raises

    async def stop(self) -> None:
        self.stopped = True


class FakeMarketRuntime:
    def __init__(self, log: list[str], markets: tuple[str, ...] = ("mkt_1",)) -> None:
        self.log = log
        self.markets = markets
        self.reconcile_calls = 0
        self.stopped = False
        self.reconcile_raises: Exception | None = None
        self.callback_failures = {"on_state": 0, "on_connection": 0}

    async def reconcile_demand_once(self) -> None:
        self.log.append("market.reconcile")
        self.reconcile_calls += 1
        if self.reconcile_raises is not None:
            raise self.reconcile_raises

    def active_market_ids(self) -> tuple[str, ...]:
        return tuple(self.markets)

    async def stop(self) -> None:
        self.stopped = True


class FakeStateRepo:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.saved: list[object] = []
        self.raise_error: Exception | None = None

    async def save_health(self, health) -> None:
        if self.raise_error is not None:
            raise self.raise_error
        self.log.append("persist")
        self.saved.append(health)


def make_daemon(
    clock: FakeClock | None = None, *, tick_seconds: float = 1.0, **overrides
):
    log: list[str] = []
    clock = clock or FakeClock()
    state = FakeStateRepo(log)
    registry = RuntimeHealthRegistry(state=state, clock=clock.now)
    parts = {
        "log": log,
        "clock": clock,
        "state": state,
        "health": registry,
        "realtime": FakeRealtime(log),
        "market_worker": FakeMarketRuntime(log),
        "decision_worker": RecordingDecisionWorker(log),
        "paper": RecordingPaper(log),
        "hot_books": FakeHotBooks(),
        "market_provider": FakeMarketProvider(log),
        "markets": FakeMarketsRepo(),
        "ledger": FakeLedger(log),
        "catalog_provider": FakeCatalogProvider(log),
        "catalog_store": FakeCatalogStore(log),
        "directory": FakeDirectory(log),
        "resolver": FakeResolver(
            {
                "ply_a": make_player("ply_a", "Player One"),
                "ply_b": make_player("ply_b", "Player Two"),
            }
        ),
        "metrics": P3Metrics(),
    }
    parts.update(overrides)
    daemon = LocalRuntimeDaemon(
        realtime=parts["realtime"],
        market_worker=parts["market_worker"],
        decision_worker=parts["decision_worker"],
        health=parts["health"],
        clock=clock.now,
        paper=parts["paper"],
        hot_books=parts["hot_books"],
        market_provider=parts["market_provider"],
        markets=parts["markets"],
        ledger=parts["ledger"],
        catalog_provider=parts["catalog_provider"],
        catalog_store=parts["catalog_store"],
        directory=parts["directory"],
        resolver=parts["resolver"],
        metrics=parts["metrics"],
        tick_seconds=tick_seconds,
    )
    return daemon, parts


# ---------------------------------------------------------------------------
# Bounded scheduling: the exact default intervals from the brief
# ---------------------------------------------------------------------------


async def test_scheduler_runs_catalog_and_market_jobs_at_bounded_intervals():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    catalog: FakeCatalogProvider = parts["catalog_provider"]

    await daemon.tick_once()
    clock.advance(seconds=59)
    await daemon.tick_once()
    assert catalog.live_calls == 1
    clock.advance(seconds=1)
    await daemon.tick_once()
    assert catalog.live_calls == 2

    # Market discovery is bounded at 120s: two ticks inside the window ran it
    # exactly once.
    provider: FakeMarketProvider = parts["market_provider"]
    assert provider.discovery_calls == 1
    clock.advance(seconds=59)
    await daemon.tick_once()
    assert provider.discovery_calls == 1
    clock.advance(seconds=1)
    await daemon.tick_once()
    assert provider.discovery_calls == 2

    # Upcoming catalog (600s) has not repeated yet.
    assert catalog.fixture_calls == 1


async def test_rankings_job_respects_the_daily_bound():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    directory: FakeDirectory = parts["directory"]

    await daemon.tick_once()
    assert directory.rankings_calls == 1

    clock.advance(seconds=86_399)
    await daemon.tick_once()
    assert directory.rankings_calls == 1

    clock.advance(seconds=1)
    await daemon.tick_once()
    assert directory.rankings_calls == 2


async def test_resolution_recheck_never_runs_more_often_than_discovery():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    ledger: FakeLedger = parts["ledger"]

    await daemon.tick_once()
    assert ledger.unsettled_calls == 1

    clock.advance(seconds=60)
    await daemon.tick_once()
    assert ledger.unsettled_calls == 1

    clock.advance(seconds=60)
    await daemon.tick_once()
    assert ledger.unsettled_calls == 2


async def test_tick_once_follows_the_exact_bounded_sequence():
    daemon, parts = make_daemon()

    await daemon.tick_once()

    assert parts["log"] == [
        "realtime.reconcile",
        "market.reconcile",
        "pump:mkt_1",
        "intents:mkt_1",
        "job:live_catalog",
        "job:upcoming_catalog",
        "job:rankings",
        "job:market_discovery",
        "job:resolution_recheck",
        "persist",
    ]


# ---------------------------------------------------------------------------
# Failure containment: degrade health, never crash, never delete data
# ---------------------------------------------------------------------------


def test_stable_reason_code_sanitizes_exceptions():
    assert (
        stable_reason_code(AppError("provider_unavailable", "down", 502))
        == "PROVIDER_UNAVAILABLE"
    )
    assert stable_reason_code(RuntimeError("boom")) == "RUNTIME_ERROR"

    class WeirdBoom(Exception):
        pass

    assert stable_reason_code(WeirdBoom("x")) == "WEIRD_BOOM"


async def test_job_failure_degrades_health_without_crashing_or_deleting():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    catalog: FakeCatalogProvider = parts["catalog_provider"]
    store: FakeCatalogStore = parts["catalog_store"]
    state: FakeStateRepo = parts["state"]
    catalog.live_matches = [make_match("mat_keep")]
    await daemon.tick_once()
    assert "mat_keep" in store.rows

    catalog.raise_on_live = RuntimeError("provider_down")
    catalog.live_matches = []
    clock.advance(seconds=60)
    await daemon.tick_once()

    health = state.saved[-1]
    source = health.sources["live_catalog"]
    assert source.status is RuntimeSourceStatus.DEGRADED
    assert source.reason_code == "RUNTIME_ERROR"
    # Prior canonical data is preserved even though the fetch failed.
    assert "mat_keep" in store.rows
    # Other jobs still ran and the tick persisted.
    assert parts["directory"].rankings_calls == 1
    assert parts["log"][-1] == "persist"

    catalog.raise_on_live = None
    clock.advance(seconds=60)
    await daemon.tick_once()
    health = state.saved[-1]
    assert health.sources["live_catalog"].status is RuntimeSourceStatus.OK
    assert health.sources["live_catalog"].reason_code is None


async def test_provider_error_codes_map_to_stable_reason_codes():
    daemon, parts = make_daemon()
    catalog: FakeCatalogProvider = parts["catalog_provider"]
    state: FakeStateRepo = parts["state"]
    catalog.raise_on_live = AppError("provider_unavailable", "upstream down", 502)

    await daemon.tick_once()

    source = state.saved[-1].sources["live_catalog"]
    assert source.status is RuntimeSourceStatus.DEGRADED
    assert source.reason_code == "PROVIDER_UNAVAILABLE"


async def test_rankings_report_with_failures_degrades_the_job():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    parts["directory"].report = DirectorySyncReport(discovered=10, failed=2)

    await daemon.tick_once()

    source = state.saved[-1].sources["rankings"]
    assert source.status is RuntimeSourceStatus.DEGRADED
    assert source.reason_code == "RANKINGS_SYNC_FAILED"


async def test_catalog_jobs_sync_aliases_for_newly_seen_players():
    daemon, parts = make_daemon()
    store: FakeCatalogStore = parts["catalog_store"]
    directory: FakeDirectory = parts["directory"]
    store.newly_seen = {"ply_b", "ply_a"}
    parts["catalog_provider"].live_matches = [make_match()]

    await daemon.tick_once()

    assert directory.alias_calls == [("ply_a", "ply_b")]


# ---------------------------------------------------------------------------
# Discovery: canonical saves, strict mapping only, rules capture
# ---------------------------------------------------------------------------


async def test_discovery_saves_canonical_markets_and_only_strict_links():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    store: FakeCatalogStore = parts["catalog_store"]
    state: FakeStateRepo = parts["state"]
    store.rows["mat_1"] = make_match("mat_1")
    mapped = make_provider_market("mkt_mapped")
    unmapped = make_provider_market(
        "mkt_unmapped",
        player_a="ply_z",
        player_b="ply_y",
        name_a="Unknown One",
        name_b="Unknown Two",
    )
    provider.markets = [mapped, unmapped]
    provider.rules = {"mkt_mapped": make_rules("mkt_mapped")}
    provider.rules_missing = {"mkt_unmapped"}

    await daemon.tick_once()

    # Canonical markets are saved regardless of mapping outcome.
    assert repo.saved_markets == ["mkt_mapped", "mkt_unmapped"]
    # Only the strict mapping produced a link; the failed mapping stays
    # MARKET_ONLY (no link, no fuzzy/manual fallback).
    assert repo.links == [("mkt_mapped", "mat_1")]
    evidence = repo.link_evidence[0]
    assert set(evidence["player_ids"]) == {"ply_a", "ply_b"}
    assert evidence["candidate_count"] == 1
    assert "http" not in json.dumps(evidence).lower()
    # Rules were captured for the mapped market; a not_found rules response
    # for the unmapped market is tolerated.
    assert repo.saved_rules == ["mkt_mapped"]
    assert state.saved[-1].sources["market_discovery"].status is RuntimeSourceStatus.OK


async def test_discovery_is_idempotent_for_identical_links():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    parts["catalog_store"].rows["mat_1"] = make_match("mat_1")
    provider.markets = [make_provider_market("mkt_mapped")]
    provider.rules = {"mkt_mapped": make_rules("mkt_mapped")}

    await daemon.tick_once()
    assert repo.links == [("mkt_mapped", "mat_1")]

    repo.active_links_rows = [LinkRow("mkt_mapped", "mat_1")]
    clock.advance(seconds=120)
    await daemon.tick_once()

    # evaluate_link_change says NOOP: the identical link is not rewritten.
    assert repo.links == [("mkt_mapped", "mat_1")]


async def test_frozen_link_does_not_abort_discovery():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    state: FakeStateRepo = parts["state"]
    parts["catalog_store"].rows["mat_1"] = make_match("mat_1")
    provider.markets = [make_provider_market("mkt_mapped")]
    provider.rules = {"mkt_mapped": make_rules("mkt_mapped")}
    repo.frozen = {"mkt_mapped"}

    await daemon.tick_once()

    assert repo.links == []
    assert state.saved[-1].sources["market_discovery"].status is RuntimeSourceStatus.OK
    assert parts["log"][-1] == "persist"


# ---------------------------------------------------------------------------
# Resolution / rules recheck: bounded targets, FINAL-only routing
# ---------------------------------------------------------------------------


async def test_resolution_targets_cover_active_unsettled_and_recently_closed():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    ledger: FakeLedger = parts["ledger"]
    repo.active_links_rows = [LinkRow("mkt_a", "mat_a")]
    ledger.unsettled = {"mkt_u"}
    provider.markets = [
        make_provider_market("mkt_c", status=MarketStatus.CLOSED),
        make_provider_market("mkt_open"),
    ]
    provider.rules_missing = {"mkt_c", "mkt_open"}

    await daemon.tick_once()

    assert set(provider.resolution_calls) == {"mkt_a", "mkt_u", "mkt_c"}


async def test_only_final_resolutions_route_through_decision_worker():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    ledger: FakeLedger = parts["ledger"]
    decision: RecordingDecisionWorker = parts["decision_worker"]
    repo.active_links_rows = [LinkRow("mkt_final", "mat_f")]
    ledger.unsettled = {"mkt_pending"}
    final = make_resolution("mkt_final")
    provider.resolutions = {
        "mkt_final": final,
        "mkt_pending": make_resolution("mkt_pending", status=ResolutionStatus.PENDING),
    }

    await daemon.tick_once()

    assert decision.resolutions == [("mkt_final", final)]


async def test_resolution_targets_are_capped():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    ledger: FakeLedger = parts["ledger"]
    ledger.unsettled = {f"mkt_{i:03d}" for i in range(40)}

    await daemon.tick_once()

    assert len(provider.resolution_calls) == 32
    assert set(provider.resolution_calls) <= ledger.unsettled


async def test_recently_closed_markets_leave_the_recheck_window():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    provider: FakeMarketProvider = parts["market_provider"]
    provider.markets = [make_provider_market("mkt_c", status=MarketStatus.CLOSED)]
    provider.rules_missing = {"mkt_c"}

    await daemon.tick_once()
    assert "mkt_c" in provider.resolution_calls

    provider.markets = []
    provider.resolution_calls.clear()
    clock.advance(seconds=25 * 3600)
    await daemon.tick_once()

    assert provider.resolution_calls == []


async def test_unsettled_positions_outrank_active_links_under_the_cap():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    repo: FakeMarketsRepo = parts["markets"]
    ledger: FakeLedger = parts["ledger"]
    repo.active_links_rows = [
        LinkRow(f"mkt_a{i:03d}", f"mat_{i}") for i in range(39)
    ] + [LinkRow("mkt_u1", "mat_u1")]
    ledger.unsettled = {"mkt_u1", "mkt_u2"}

    await daemon.tick_once()

    calls = set(provider.resolution_calls)
    # Unsettled positions are always polled even though active links alone
    # overflow the cap of 32.
    assert {"mkt_u1", "mkt_u2"} <= calls
    assert len(provider.resolution_calls) == 32
    # mkt_u1 is deduplicated into the unsettled class, so only 30 of the 39
    # remaining active links fit beside the two unsettled markets.
    assert len(calls & {f"mkt_a{i:03d}" for i in range(39)}) == 30


async def test_overflowing_resolution_targets_rotate_to_full_coverage():
    unsettled = {f"mkt_{i:03d}" for i in range(40)}
    cycles_a: list[tuple[str, ...]] = []
    cycles_b: list[tuple[str, ...]] = []
    for record in (cycles_a, cycles_b):
        daemon, parts = make_daemon()
        clock: FakeClock = parts["clock"]
        provider: FakeMarketProvider = parts["market_provider"]
        parts["ledger"].unsettled = set(unsettled)
        for cycle in range(5):
            if cycle:
                clock.advance(seconds=120)
            provider.resolution_calls.clear()
            await daemon.tick_once()
            assert len(provider.resolution_calls) == 32
            record.append(tuple(provider.resolution_calls))

    # Deterministic: identical input sets and call counts give identical
    # per-cycle polling order.
    assert cycles_a == cycles_b
    # Rotation reaches every overflowed target within a bounded cycle count.
    polled: set[str] = set().union(*cycles_a)
    assert polled == unsettled


async def test_skipped_resolution_targets_counter_reports_the_overflow():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    parts["ledger"].unsettled = {f"mkt_{i:03d}" for i in range(40)}

    await daemon.tick_once()

    assert state.saved[-1].counters["resolution_targets_skipped"] == 8

    # Below the cap nothing is skipped.
    small, small_parts = make_daemon()
    small_parts["ledger"].unsettled = {"mkt_x", "mkt_y"}
    await small.tick_once()
    assert small_parts["state"].saved[-1].counters["resolution_targets_skipped"] == 0


# ---------------------------------------------------------------------------
# Paper maintenance: canonical hot book + metadata, fail-closed to None
# ---------------------------------------------------------------------------


async def test_execute_due_intents_uses_hot_book_and_caches_metadata():
    daemon, parts = make_daemon()
    clock: FakeClock = parts["clock"]
    provider: FakeMarketProvider = parts["market_provider"]
    paper: RecordingPaper = parts["paper"]
    parts["hot_books"].books["mkt_1"] = make_book("mkt_1")
    provider.metadata["mkt_1"] = INPUTS["metadata"]

    await daemon.tick_once()
    assert paper.calls == [("mkt_1", True, True)]
    assert provider.metadata_calls == ["mkt_1"]

    clock.advance(seconds=1)
    await daemon.tick_once()
    assert len(paper.calls) == 2
    # Metadata is fetched at most once per discovery interval.
    assert provider.metadata_calls == ["mkt_1"]

    clock.advance(seconds=120)
    await daemon.tick_once()
    assert len(provider.metadata_calls) == 2


async def test_metadata_failure_passes_none_and_degrades_paper_health():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    paper: RecordingPaper = parts["paper"]
    state: FakeStateRepo = parts["state"]
    parts["hot_books"].books["mkt_1"] = make_book("mkt_1")
    provider.metadata_raises = AppError("provider_invalid_response", "bad", 502)

    await daemon.tick_once()

    # Never manufacture a fill: None lets BOOK_UNVERIFIABLE/NO_FILL apply.
    assert paper.calls == [("mkt_1", True, False)]
    source = state.saved[-1].sources["paper_execution"]
    assert source.status is RuntimeSourceStatus.DEGRADED
    assert source.reason_code == "PROVIDER_INVALID_RESPONSE"


async def test_missing_hot_book_passes_none_without_metadata_fetch():
    daemon, parts = make_daemon()
    provider: FakeMarketProvider = parts["market_provider"]
    paper: RecordingPaper = parts["paper"]

    await daemon.tick_once()

    assert paper.calls == [("mkt_1", False, False)]
    assert provider.metadata_calls == []


async def test_hot_book_failure_degrades_paper_health_and_passes_none():
    daemon, parts = make_daemon()
    paper: RecordingPaper = parts["paper"]
    state: FakeStateRepo = parts["state"]
    parts["hot_books"].raise_error = AppError("redis_unavailable", "down", 503)

    await daemon.tick_once()

    assert paper.calls == [("mkt_1", False, False)]
    assert state.saved[-1].sources["paper_execution"].reason_code == "REDIS_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Bridges: worker hooks into health + decision worker
# ---------------------------------------------------------------------------


async def test_market_bridge_dedupes_identical_baselines():
    daemon, parts = make_daemon()
    decision: RecordingDecisionWorker = parts["decision_worker"]
    bridge = MarketBridge(decision_worker=decision, health=parts["health"])
    state = make_book("mkt_1")

    await bridge.on_state("mkt_1", state)
    await bridge.on_state("mkt_1", state)
    assert decision.submitted == [("mkt_1", state)]
    assert bridge.duplicates == 1

    changed = state.model_copy(update={"book_hash": "book_v8"})
    await bridge.on_state("mkt_1", changed)
    assert len(decision.submitted) == 2


async def test_bridges_map_connection_states_to_gap_and_recovery():
    daemon, parts = make_daemon()
    health: RuntimeHealthRegistry = parts["health"]
    sports = SportsBridge(decision_worker=parts["decision_worker"], health=health)
    markets = MarketBridge(decision_worker=parts["decision_worker"], health=health)

    await markets.on_connection("mkt_1", "reconnecting")
    assert (await health.freshness_for("mat_1", "mkt_1")).has_gap is True
    await markets.on_connection("mkt_1", "live")
    assert (await health.freshness_for("mat_1", "mkt_1")).has_gap is False

    await sports.on_connection("mat_1", "reconnecting")
    assert (await health.freshness_for("mat_1", None)).has_gap is True
    await sports.on_connection("mat_1", "live")
    assert (await health.freshness_for("mat_1", None)).has_gap is False

    snapshot = object()
    await sports.on_snapshot("mat_1", snapshot)
    assert parts["decision_worker"].sports == [("mat_1", snapshot)]


async def test_tracking_demand_source_isolates_failures_and_falls_back():
    daemon, parts = make_daemon()
    health: RuntimeHealthRegistry = parts["health"]

    class Tracking:
        def __init__(self) -> None:
            self.demanded = {"mkt_1"}
            self.raise_next = False

        async def demanded_markets(self) -> set[str]:
            if self.raise_next:
                raise RuntimeError("db_down")
            return set(self.demanded)

    tracking = Tracking()
    links = MarketRepositoryLinks(
        FakeLinkRepo([LinkRow("mkt_1", "mat_1"), LinkRow("mkt_2", "mat_2")])
    )
    source = TrackingDemandSource(
        tracking=tracking, links=links, health=health, source="p3_tracking"
    )

    assert await source() == {"mat_1": "active"}

    tracking.raise_next = True
    # A P3 tracking DB failure must never abort the viewer cycle.
    assert await source() == {"mat_1": "active"}
    persisted = await health.persist()
    degraded = persisted.sources["p3_tracking"]
    assert degraded.status is RuntimeSourceStatus.DEGRADED
    assert degraded.reason_code == "RUNTIME_ERROR"


# ---------------------------------------------------------------------------
# Health surface unification: pipeline counters flow into persist()
# ---------------------------------------------------------------------------


async def test_counters_aggregate_pipeline_metrics_into_health():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    metrics: P3Metrics = parts["metrics"]
    metrics.increment("decision_suppressed")
    parts["realtime"].callback_failures = {"on_snapshot": 2, "on_connection": 0}
    parts["market_worker"].callback_failures = {"on_state": 1, "on_connection": 1}
    parts["decision_worker"].overflow = 3

    await daemon.tick_once()

    counters = state.saved[-1].counters
    assert counters["decision_suppressed"] == 1
    assert counters["realtime_callback_failures"] == 2
    assert counters["market_callback_failures"] == 2
    assert counters["decision_queue_overflow"] == 3


# ---------------------------------------------------------------------------
# Recovery: explicit gap first, durable rebuild, retry on failure
# ---------------------------------------------------------------------------


async def test_recover_once_writes_gap_before_recovery_then_restores():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    health: RuntimeHealthRegistry = parts["health"]
    decision: RecordingDecisionWorker = parts["decision_worker"]
    parts["markets"].active_links_rows = [LinkRow("mkt_1", "mat_1")]

    await daemon.recover_once()

    # An explicit gap is persisted BEFORE any recovery work succeeds.
    first = state.saved[0]
    assert first.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.GAP
    assert first.sources[SPORTS_SOURCE].reason_code == RECOVERY_REASON
    assert first.sources[MARKET_SOURCE].status is RuntimeSourceStatus.GAP
    assert first.sources[MARKET_SOURCE].reason_code == RECOVERY_REASON

    # Durable demand rebuilt cursors and both workers reconciled via REST.
    assert decision.recovered == [frozenset({"mat_1"})]
    assert parts["realtime"].reconcile_calls == 1
    assert parts["market_worker"].reconcile_calls == 1

    # After success the gap is lifted and persisted.
    assert (await health.freshness_for("mat_1", "mkt_1")).has_gap is False
    final = state.saved[-1]
    assert final.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.OK
    assert final.sources[MARKET_SOURCE].status is RuntimeSourceStatus.OK
    assert final.sources[MARKET_SOURCE].last_tracked == 1
    assert daemon.recovered is True


async def test_recover_once_keeps_gap_and_retries_when_reconciliation_fails():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    health: RuntimeHealthRegistry = parts["health"]
    parts["realtime"].reconcile_raises = RuntimeError("db_down")

    await daemon.recover_once()

    assert daemon.recovered is False
    assert (await health.freshness_for("mat_1", None)).has_gap is True
    assert (await health.freshness_for("mat_1", "mkt_1")).has_gap is True
    degraded = state.saved[-1].sources["recovery"]
    assert degraded.status is RuntimeSourceStatus.DEGRADED
    assert degraded.reason_code == "RUNTIME_ERROR"

    parts["realtime"].reconcile_raises = None
    await daemon.recover_once()

    assert daemon.recovered is True
    assert (await health.freshness_for("mat_1", None)).has_gap is False


async def test_recover_once_survives_persist_failure_and_repersists_later():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    health: RuntimeHealthRegistry = parts["health"]
    state.raise_error = RuntimeError("db_down")

    # A failing state persist never aborts recovery nor escapes to run().
    await daemon.recover_once()

    assert daemon.recovered is True
    assert state.saved == []

    # Once the database returns, persisting writes the same truthful state.
    state.raise_error = None
    await health.persist()

    final = state.saved[-1]
    assert final.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.OK
    assert final.sources[MARKET_SOURCE].status is RuntimeSourceStatus.OK


async def test_recover_once_degraded_path_survives_persist_failure():
    daemon, parts = make_daemon()
    state: FakeStateRepo = parts["state"]
    state.raise_error = RuntimeError("db_down")
    parts["realtime"].reconcile_raises = RuntimeError("db_down")

    # Both reconciliation and the degraded-path persist fail: recovery must
    # return quietly and stay retryable.
    await daemon.recover_once()

    assert daemon.recovered is False
    assert state.saved == []

    state.raise_error = None
    parts["realtime"].reconcile_raises = None
    await daemon.recover_once()

    assert daemon.recovered is True
    assert len(state.saved) >= 1


# ---------------------------------------------------------------------------
# Run loop and graceful shutdown
# ---------------------------------------------------------------------------


async def test_run_loop_ticks_until_stop_and_shuts_down_gracefully():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=0.01)

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=2)

    assert parts["realtime"].reconcile_calls >= 2
    assert parts["realtime"].stopped is True
    assert parts["market_worker"].stopped is True
    # Shutdown persists the final health state; nothing is deleted.
    assert parts["log"][-1] == "persist"
    assert len(parts["state"].saved) >= 2


async def test_run_loop_survives_repeated_tick_failures():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=0.01)
    parts["realtime"].reconcile_raises = RuntimeError("ws_down")

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=2)

    degraded = parts["state"].saved[-1].sources["daemon_tick"]
    assert degraded.status is RuntimeSourceStatus.DEGRADED
    assert degraded.reason_code == "RUNTIME_ERROR"


async def test_run_loop_restores_tick_health_after_a_transient_failure():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=0.01)
    state: FakeStateRepo = parts["state"]
    parts["realtime"].reconcile_raises = RuntimeError("db_blip")

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)

    degraded = state.saved[-1].sources["daemon_tick"]
    assert degraded.status is RuntimeSourceStatus.DEGRADED
    assert degraded.reason_code == "RUNTIME_ERROR"

    # The blip passes: clean ticks clear the degradation, so neither the
    # registry nor the persisted payload `status` reads keeps reporting a
    # stale RUNTIME_ERROR while the daemon ticks fine.
    parts["realtime"].reconcile_raises = None
    await asyncio.sleep(0.05)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=2)

    restored = state.saved[-1].sources["daemon_tick"]
    assert restored.status is RuntimeSourceStatus.OK
    assert restored.reason_code is None

    # A fresh persist proves the in-memory registry state itself recovered.
    current = await parts["health"].persist()
    assert current.sources["daemon_tick"].status is RuntimeSourceStatus.OK
    assert current.sources["daemon_tick"].reason_code is None


async def test_run_loop_survives_state_persist_failures():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=0.01)
    state: FakeStateRepo = parts["state"]
    state.raise_error = RuntimeError("db_down")

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    # Recovery and repeated ticks keep running even though every persist —
    # including the degraded handler's own — fails against the state store.
    assert daemon.recovered is True
    assert parts["realtime"].reconcile_calls >= 2
    assert state.saved == []

    # Once the database returns, the loop re-persists truthful health.
    state.raise_error = None
    await asyncio.sleep(0.05)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=2)

    assert len(state.saved) >= 1
    final = state.saved[-1]
    assert final.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.OK
    assert parts["log"][-1] == "persist"


async def test_stop_survives_state_persist_failure():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=0.01)
    parts["state"].raise_error = RuntimeError("db_down")

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    # Shutdown completes (sockets closed, loop exits) even when the final
    # health persist cannot reach the state store.
    await daemon.stop()
    await asyncio.wait_for(task, timeout=2)

    assert parts["realtime"].stopped is True
    assert parts["market_worker"].stopped is True


async def test_run_loop_cancellation_still_propagates():
    clock = FakeClock()
    daemon, parts = make_daemon(clock, tick_seconds=30)

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    task.cancel()
    # Persist/recovery suppression never swallows CancelledError.
    with pytest.raises(asyncio.CancelledError):
        await task
