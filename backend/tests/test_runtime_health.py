"""Runtime health registry tests (T78).

Fresh/degraded/stale/gap semantics for the local runtime: an open,
heartbeat-confirmed sports connection stays fresh while the score is quiet;
disconnects and reconciliation periods produce a gap that revokes new
BUY/SELL decisions until REST reconciliation succeeds; low-frequency job
failures degrade without deleting prior canonical data; reason codes are
sanitized stable codes; and `persist()` writes one aggregate `RuntimeHealth`
(with pipeline counters and paper/model status) through the state
repository. Health payloads never carry provider identifiers or URLs.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_decision_worker import (
    FakeBookSource,
    FakeDecisionPublisher,
    FakeLinks,
    FakeObservations,
    FakePaperService,
    FakePositions,
    RecordingPredictor,
    available_prediction,
)
from tests_support import FakeClock, build_service_inputs

from app.decision.engine import DecisionEngine
from app.decision.models import DecisionAction
from app.decision.policy import PolicyArtifact
from app.decision.worker import DecisionWorker
from app.realtime.p3_metrics import P3Metrics
from app.runtime.health import (
    MARKET_SOURCE,
    RECOVERY_REASON,
    SPORTS_SOURCE,
    RuntimeHealthRegistry,
)
from app.api.schemas import RuntimeHealthDto
from app.runtime.models import MarketQuoteCoverage, RuntimeHealth, RuntimeSourceStatus
from tests.test_decision_worker import POLICY_PATH

INPUTS = build_service_inputs()


class FakeStateRepo:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save_health(self, health) -> None:
        self.saved.append(health)


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def state() -> FakeStateRepo:
    return FakeStateRepo()


@pytest.fixture()
def health(state: FakeStateRepo, clock: FakeClock) -> RuntimeHealthRegistry:
    return RuntimeHealthRegistry(state=state, clock=clock.now)


# ---------------------------------------------------------------------------
# Freshness: quiet tennis is not stale; gaps fail closed until reconciliation
# ---------------------------------------------------------------------------


async def test_score_silence_does_not_mark_a_healthy_websocket_stale(
    health: RuntimeHealthRegistry, clock: FakeClock
):
    await health.mark_success("tennis_live", tracked=1)

    clock.advance(seconds=90)

    overlay = await health.freshness_for("mat_1", None)
    assert overlay.has_gap is False
    assert overlay.is_stale is False


async def test_stale_after_bound_reports_is_stale_without_gap(
    state: FakeStateRepo, clock: FakeClock
):
    bounded = RuntimeHealthRegistry(
        state=state,
        clock=clock.now,
        stale_after={"tennis_live": timedelta(seconds=30)},
    )
    await bounded.mark_success("tennis_live", tracked=1)

    clock.advance(seconds=31)

    overlay = await bounded.freshness_for("mat_1", None)
    assert overlay.is_stale is True
    assert overlay.has_gap is False


async def test_gap_on_market_source_does_not_pollute_sports_only_overlay(
    health: RuntimeHealthRegistry,
):
    await health.mark_gap("polymarket", "CONNECTION_LOST")

    assert (await health.freshness_for("mat_1", None)).has_gap is False
    assert (await health.freshness_for("mat_1", "mkt_1")).has_gap is True


async def test_mark_recovered_only_clears_the_startup_recovery_gap(
    health: RuntimeHealthRegistry,
):
    await health.mark_gap(SPORTS_SOURCE, "CONNECTION_LOST")
    await health.mark_recovered(SPORTS_SOURCE)
    assert (await health.freshness_for("mat_1", None)).has_gap is True

    await health.mark_gap(SPORTS_SOURCE, RECOVERY_REASON)
    await health.mark_recovered(SPORTS_SOURCE)
    assert (await health.freshness_for("mat_1", None)).has_gap is False


async def test_gap_revokes_new_decision_actions_until_rest_reconciliation_succeeds(
    health: RuntimeHealthRegistry,
):
    log: list[str] = []
    predictor = RecordingPredictor()
    predictor.prediction = available_prediction()
    observations = FakeObservations(log)
    paper = FakePaperService(log)
    decision_worker = DecisionWorker(
        predictor=predictor,
        engine=DecisionEngine(policy=PolicyArtifact.load(POLICY_PATH)),
        paper=paper,
        books=FakeBookSource(),
        links=FakeLinks(),
        observations=observations,
        positions=FakePositions(),
        publisher=FakeDecisionPublisher(log),
        metrics=P3Metrics(),
        clock=FakeClock().now,
        freshness_for=health.freshness_for,
    )
    await decision_worker.handle_sports("mat_1", snapshot=None)
    assert observations.saved[-1].action is DecisionAction.BUY

    await health.mark_gap("polymarket", "CONNECTION_LOST")
    await decision_worker.handle_book("mkt_1", INPUTS["book"])

    latest = observations.saved[-1]
    assert latest.action is DecisionAction.NO_BET
    assert latest.has_gap is True
    assert latest.reason_code == "GAP"
    # The revoked cycle never reached the ledger.
    assert len(paper.decisions) == 1

    # REST reconciliation succeeds: the same book may act again.
    await health.mark_success("polymarket")
    await decision_worker.handle_book("mkt_1", INPUTS["book"])

    recovered = observations.saved[-1]
    assert recovered.has_gap is False
    assert recovered.action is DecisionAction.BUY
    assert len(paper.decisions) == 2


# ---------------------------------------------------------------------------
# Degraded semantics and sanitized reason codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["bad code", "lower_case", "1_LEADING_DIGIT", ""])
async def test_mark_degraded_rejects_unsanitized_reason_codes(
    health: RuntimeHealthRegistry, code: str
):
    with pytest.raises(ValueError):
        await health.mark_degraded("live_catalog", code)


@pytest.mark.parametrize("code", ["bad-code", "has space", "secret://leak"])
async def test_mark_gap_rejects_unsanitized_reason_codes(
    health: RuntimeHealthRegistry, code: str
):
    with pytest.raises(ValueError):
        await health.mark_gap(MARKET_SOURCE, code)


async def test_degraded_keeps_last_success_and_prior_counts(
    health: RuntimeHealthRegistry, state: FakeStateRepo, clock: FakeClock
):
    await health.mark_success("live_catalog", tracked=3)
    success_at = clock.now()
    clock.advance(seconds=120)

    await health.mark_degraded("live_catalog", "PROVIDER_TIMEOUT")

    persisted = await health.persist()
    source = persisted.sources["live_catalog"]
    assert source.status is RuntimeSourceStatus.DEGRADED
    assert source.reason_code == "PROVIDER_TIMEOUT"
    assert source.last_success_at == success_at
    assert source.success_count == 1
    assert source.failure_count == 1

    # Recovery keeps the prior canonical data path: success restores OK.
    await health.mark_success("live_catalog", tracked=4)
    persisted = await health.persist()
    source = persisted.sources["live_catalog"]
    assert source.status is RuntimeSourceStatus.OK
    assert source.reason_code is None
    assert source.success_count == 2
    assert state.saved[-1] is persisted


# ---------------------------------------------------------------------------
# Aggregate persistence: counters, paper/model status, hygiene
# ---------------------------------------------------------------------------


async def test_persist_writes_aggregate_with_counters_and_paper_model_status(
    state: FakeStateRepo, clock: FakeClock
):
    health = RuntimeHealthRegistry(
        state=state,
        clock=clock.now,
        paper_status="paper_only",
        model_status="not_promoted",
    )
    health.attach_counters(
        lambda: {"decision_suppressed": 2, "realtime_callback_failures": 1}
    )
    await health.mark_success(SPORTS_SOURCE, tracked=2)
    await health.mark_gap(MARKET_SOURCE, "CONNECTION_LOST")

    persisted = await health.persist()

    assert state.saved == [persisted]
    assert persisted.generated_at == clock.now()
    assert persisted.sources[SPORTS_SOURCE].status is RuntimeSourceStatus.OK
    assert persisted.sources[SPORTS_SOURCE].last_tracked == 2
    assert persisted.sources[MARKET_SOURCE].status is RuntimeSourceStatus.GAP
    assert persisted.counters == {
        "decision_suppressed": 2,
        "realtime_callback_failures": 1,
    }
    assert persisted.paper_status == "paper_only"
    assert persisted.model_status == "not_promoted"


async def test_persisted_payload_stays_free_of_provider_identifiers(
    health: RuntimeHealthRegistry,
):
    await health.mark_gap(MARKET_SOURCE, "CONNECTION_LOST")
    await health.mark_degraded("live_catalog", "PROVIDER_TIMEOUT")

    persisted = await health.persist()
    payload = persisted.model_dump_json()

    assert "://" not in payload
    assert "http" not in payload.lower()
    assert "990001112223334445551" not in payload
    for source in persisted.sources.values():
        assert (
            source.reason_code is None or source.reason_code.replace("_", "").isalnum()
        )


# ---------------------------------------------------------------------------
# P4.3 coverage lane: aggregate market quote coverage (T86)
# ---------------------------------------------------------------------------


async def test_market_coverage_is_persisted_as_aggregate_counts(
    health: RuntimeHealthRegistry, state: FakeStateRepo, clock: FakeClock
):
    coverage = MarketQuoteCoverage(
        generated_at=clock.now(),
        candidate=181,
        attempted=181,
        fresh_snapshot=150,
        no_liquidity=20,
        unavailable=11,
        last_successful_batch_at=clock.now(),
    )
    health.set_market_coverage(coverage)

    persisted = await health.persist()

    assert persisted.market_coverage is not None
    assert persisted.market_coverage.candidate == 181
    assert persisted.market_coverage.fresh_snapshot == 150
    assert state.saved[-1].market_coverage.candidate == 181
    dto = RuntimeHealthDto.model_validate(persisted.model_dump())
    assert dto.market_coverage is not None
    assert dto.market_coverage.no_liquidity == 20
    # Aggregate counts only: no token, URL, host or provider identity.
    blob = persisted.model_dump_json().lower()
    for fragment in ("token", "condition", "0x", "http", "wss", "@"):
        assert fragment not in blob


async def test_market_coverage_is_absent_until_a_round_runs(
    state: FakeStateRepo, clock: FakeClock
):
    health = RuntimeHealthRegistry(state=state, clock=clock.now)
    assert (await health.persist()).market_coverage is None

    health.set_market_coverage(
        MarketQuoteCoverage(generated_at=clock.now(), candidate=3)
    )
    payload = (await health.persist()).model_dump()
    restored = RuntimeHealth.model_validate(payload)
    assert restored.market_coverage is not None
    assert restored.market_coverage.candidate == 3


def test_market_coverage_requires_timezone_aware_timestamps():
    with pytest.raises(ValidationError):
        MarketQuoteCoverage(generated_at=datetime(2026, 9, 22, 8, 0))
    with pytest.raises(ValidationError):
        MarketQuoteCoverage(
            generated_at=datetime(2026, 9, 22, 8, 0, tzinfo=UTC),
            retry_after_until=datetime(2026, 9, 22, 8, 0),
        )
