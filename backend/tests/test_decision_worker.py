"""Decision worker orchestration tests (T65).

Ordering contract: a canonical sports change runs prediction then decision;
a valid book change reuses the latest prediction and runs quote/decision
only; rule changes suppress actions; resolutions trigger settlement; ledger
commits precede publishes. Queues are bounded and coalesce deterministically.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.decision.models import DecisionAction
from app.decision.worker import DecisionWorker
from app.realtime.p3_metrics import P3Metrics
from tests_support import FakeClock, build_service_inputs

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent / "fixtures" / "decision" / "policy-v1.json"

INPUTS = build_service_inputs()


class RecordingPredictor:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.prediction = None

    async def predict_snapshot(self, match_id: str, snapshot):
        self.calls.append(match_id)
        return self.prediction


class FakeBookSource:
    def __init__(self) -> None:
        self.book = INPUTS["book"]
        self.metadata = INPUTS["metadata"]
        self.rules_hash = "rules_v1"
        self.frozen_rules_hash: str | None = None

    async def get_book(self, market_id: str):
        return self.book

    async def get_metadata(self, market_id: str):
        return self.metadata

    async def get_rules_hash(self, market_id: str):
        return self.rules_hash

    async def get_frozen_rules_hash(self, match_id: str):
        return self.frozen_rules_hash


class FakeLinks:
    def __init__(self, match_id: str = "mat_1", market_id: str = "mkt_1") -> None:
        self._match_id = match_id
        self._market_id = market_id

    async def market_for_match(self, match_id: str):
        return self._market_id if match_id == self._match_id else None

    async def match_for_market(self, market_id: str):
        return self._match_id if market_id == self._market_id else None


class FakeObservations:
    def __init__(self, log: list[str] | None = None) -> None:
        self.saved: list[object] = []
        self.log: list[str] = log if log is not None else []

    async def save_decision_observation(self, observation) -> None:
        self.saved.append(observation)
        self.log.append("commit:decision")

    async def latest_observation_version(self, match_id: str) -> int:
        return len(self.saved)


class FakePositions:
    def __init__(self) -> None:
        self.position = None

    async def get_position(self, match_id: str):
        return self.position


class FakeDecisionPublisher:
    def __init__(self, log: list[str]) -> None:
        self.published: list[object] = []
        self._log = log

    async def publish_decision(self, observation) -> None:
        self.published.append(observation)
        self._log.append("publish:decision")


class FakePaperService:
    def __init__(self, log: list[str]) -> None:
        self.decisions: list[object] = []
        self.settled: list[tuple[str, object]] = []
        self._log = log

    async def on_decision(self, observation, **kwargs) -> None:
        self._log.append("commit:ledger")
        self.decisions.append(observation)

    async def settle_market(self, market_id, resolution, **kwargs) -> None:
        self._log.append("commit:settlement")
        self.settled.append((market_id, resolution))


def available_prediction():
    from app.prediction.models import (
        ModelAvailability,
        PredictionSnapshot,
        ProbabilityEstimate,
    )

    return PredictionSnapshot(
        match_id="mat_1",
        outcomes=(
            ProbabilityEstimate(
                player_id="ply_a", probability=0.62, lower=0.56, upper=0.68
            ),
            ProbabilityEstimate(
                player_id="ply_b", probability=0.38, lower=0.32, upper=0.44
            ),
        ),
        availability=ModelAvailability.AVAILABLE,
        model_version="m",
        calibration_version="c",
        data_version="d",
        input_state_version=4,
        as_of=NOW,
    )


@pytest.fixture()
def env():
    return make_env()


def make_env(freshness_for=None):
    from app.decision.engine import DecisionEngine
    from app.decision.policy import PolicyArtifact

    log: list[str] = []
    clock = FakeClock(NOW)
    predictor = RecordingPredictor()
    predictor.prediction = available_prediction()
    observations = FakeObservations(log)
    worker = DecisionWorker(
        predictor=predictor,
        engine=DecisionEngine(policy=PolicyArtifact.load(POLICY_PATH)),
        paper=FakePaperService(log),
        books=FakeBookSource(),
        links=FakeLinks(),
        observations=observations,
        positions=FakePositions(),
        publisher=FakeDecisionPublisher(log),
        metrics=P3Metrics(),
        clock=clock.now,
        freshness_for=freshness_for,
    )
    return {
        "worker": worker,
        "predictor": predictor,
        "clock": clock,
        "log": log,
        "books": worker._books,  # noqa: SLF001 - test introspection
        "observations": observations,
        "publisher": worker._publisher,  # noqa: SLF001
        "paper": worker._paper,  # noqa: SLF001
        "metrics": worker._metrics,  # noqa: SLF001
    }


class StubOverlay:
    def __init__(self, *, is_stale: bool = False, has_gap: bool = False) -> None:
        self.is_stale = is_stale
        self.has_gap = has_gap
        self.reason_code = "STALE" if is_stale else "GAP" if has_gap else None


class StubFreshness:
    def __init__(self, overlay: StubOverlay) -> None:
        self._overlay = overlay
        self.calls: list[tuple[str, str | None]] = []

    async def __call__(self, match_id: str, market_id: str | None) -> StubOverlay:
        self.calls.append((match_id, market_id))
        return self._overlay


async def test_sports_update_runs_prediction_then_decision(env):
    worker = env["worker"]

    await worker.handle_sports("mat_1", snapshot=None)

    assert env["predictor"].calls == ["mat_1"]
    saved = env["observations"].saved
    assert len(saved) == 1
    assert saved[0].action is DecisionAction.BUY
    assert saved[0].observation_version == 1


async def test_ledger_commit_precedes_decision_publish(env):
    worker = env["worker"]

    await worker.handle_sports("mat_1", snapshot=None)

    log = env["log"]
    assert log.index("commit:decision") < log.index("publish:decision")
    # The BUY reached the paper service (ledger) before the publish.
    assert "commit:ledger" in log
    assert log.index("commit:ledger") < log.index("publish:decision")


async def test_book_update_reuses_prediction_without_model_call(env):
    worker = env["worker"]
    await worker.handle_sports("mat_1", snapshot=None)
    env["predictor"].calls.clear()

    await worker.handle_book("mkt_1", env["books"].book)

    assert env["predictor"].calls == []
    saved = env["observations"].saved
    assert len(saved) == 2
    assert saved[1].observation_version == 2


async def test_book_update_without_prediction_never_calls_model(env):
    worker = env["worker"]

    await worker.handle_book("mkt_1", env["books"].book)

    assert env["predictor"].calls == []
    assert env["observations"].saved == []


async def test_rule_change_suppresses_actions(env):
    worker = env["worker"]
    env["books"].frozen_rules_hash = "rules_v0"
    env["books"].rules_hash = "rules_v1"

    await worker.handle_sports("mat_1", snapshot=None)

    saved = env["observations"].saved
    assert saved[0].action is DecisionAction.NO_BET
    assert saved[0].reason_code == "RULE_CHANGED"
    assert env["paper"].decisions == []


async def test_resolution_routes_to_settlement(env):
    worker = env["worker"]
    resolution = object()

    await worker.on_resolution("mkt_1", resolution)

    assert env["paper"].settled == [("mkt_1", resolution)]


async def test_bounded_queue_coalesces_to_newest_book(env):
    worker = env["worker"]
    await worker.handle_sports("mat_1", snapshot=None)
    env["observations"].saved.clear()

    for index in range(5):
        await worker.submit_book("mkt_1", env["books"].book)

    assert worker.backlog("mkt_1") <= worker.queue_capacity
    await worker.pump_once("mkt_1")

    # Five queued book updates collapse into a single decision cycle.
    assert len(env["observations"].saved) == 1


async def test_metrics_record_stage_latencies_without_ids(env):
    worker = env["worker"]

    await worker.handle_sports("mat_1", snapshot=None)
    await worker.handle_book("mkt_1", env["books"].book)

    metrics = env["metrics"]
    assert metrics.count("canonical_to_prediction") >= 1
    assert metrics.count("prediction_to_decision") >= 1
    assert metrics.count("book_to_decision") >= 1
    serialized = metrics.export()
    assert "mat_1" not in serialized
    assert "mkt_1" not in serialized
    assert "ply_" not in serialized


async def test_stale_overlay_revokes_new_buy_without_touching_the_ledger():
    freshness = StubFreshness(StubOverlay(is_stale=True))
    env = make_env(freshness_for=freshness)

    await env["worker"].handle_sports("mat_1", snapshot=None)

    assert freshness.calls == [("mat_1", "mkt_1")]
    saved = env["observations"].saved
    assert saved[-1].action is DecisionAction.NO_BET
    assert saved[-1].reason_code == "STALE"
    assert saved[-1].is_stale is True
    assert env["paper"].decisions == []


async def test_gap_overlay_revokes_new_buy_and_flags_the_observation():
    freshness = StubFreshness(StubOverlay(has_gap=True))
    env = make_env(freshness_for=freshness)

    await env["worker"].handle_sports("mat_1", snapshot=None)

    saved = env["observations"].saved
    assert saved[-1].action is DecisionAction.NO_BET
    assert saved[-1].reason_code == "GAP"
    assert saved[-1].has_gap is True
    assert env["paper"].decisions == []


async def test_default_worker_never_consults_a_freshness_callback(env):
    # Byte-compatible default: with freshness_for=None the decision cycle
    # behaves exactly as before the overlay existed.
    await env["worker"].handle_sports("mat_1", snapshot=None)

    saved = env["observations"].saved
    assert saved[-1].action is DecisionAction.BUY
    assert saved[-1].is_stale is False
    assert saved[-1].has_gap is False
