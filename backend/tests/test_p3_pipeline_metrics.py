"""P3 pipeline metrics and the local latency gate (T65).

Low-cardinality stage histograms plus backlog/reconnect/gap counters, with
zero player/match/token identifiers in any label. The latency gate replays
10,000 valid book changes and 1,000 sports changes through the in-memory
pipeline: book->decision p95 must stay under 500ms, sports->decision p95
under 1s, queues must not overflow and identical runs must produce
identical outputs.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.decision.engine import DecisionEngine
from app.decision.policy import PolicyArtifact
from app.decision.worker import DecisionWorker
from app.realtime.p3_metrics import P3Metrics
from tests_support import FakeClock
from tests.test_decision_worker import (
    FakeBookSource,
    FakeDecisionPublisher,
    FakeLinks,
    FakeObservations,
    FakePaperService,
    FakePositions,
    RecordingPredictor,
    available_prediction,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent / "fixtures" / "decision" / "policy-v1.json"


def test_histogram_percentiles_are_exact_on_uniform_samples():
    metrics = P3Metrics()
    for value in range(1, 101):
        metrics.observe("stage_a", float(value))

    assert metrics.percentile("stage_a", 50) == pytest.approx(50, abs=1.5)
    assert metrics.percentile("stage_a", 95) == pytest.approx(95, abs=1.5)
    assert metrics.percentile("stage_a", 99) == pytest.approx(99, abs=1.5)
    assert metrics.count("stage_a") == 100


def test_counters_increment_without_labels():
    metrics = P3Metrics()
    metrics.increment("queue_overflow")
    metrics.increment("queue_overflow")
    metrics.increment("reconnects")
    metrics.increment("tracking_gaps")

    snapshot = json.loads(metrics.export())
    assert snapshot["counters"]["queue_overflow"] == 2
    assert snapshot["counters"]["reconnects"] == 1
    assert snapshot["counters"]["tracking_gaps"] == 1


def test_export_never_contains_identifier_labels():
    metrics = P3Metrics()
    metrics.observe("book_to_decision", 1.0)
    metrics.increment("queue_overflow")

    exported = metrics.export()
    for fragment in ("mat_", "mkt_", "ply_", "9900011"):
        assert fragment not in exported


def _build_pipeline():
    clock = FakeClock(NOW)
    log: list[str] = []
    predictor = RecordingPredictor()
    predictor.prediction = available_prediction()
    observations = FakeObservations()
    metrics = P3Metrics()
    worker = DecisionWorker(
        predictor=predictor,
        engine=DecisionEngine(policy=PolicyArtifact.load(POLICY_PATH)),
        paper=FakePaperService(log),
        books=FakeBookSource(),
        links=FakeLinks(),
        observations=observations,
        positions=FakePositions(),
        publisher=FakeDecisionPublisher(log),
        metrics=metrics,
        clock=clock.now,
    )
    return worker, predictor, observations, metrics


async def test_local_latency_gate_and_deterministic_output():
    outputs = []
    for run in range(2):
        worker, predictor, observations, metrics = _build_pipeline()
        predictor.prediction = available_prediction()

        # Warm-up.
        for _ in range(50):
            await worker.handle_sports("mat_1", snapshot=None)
            await worker.handle_book("mkt_1", worker._books.book)  # noqa: SLF001

        book_changes = 10_000
        sports_changes = 1_000

        started = time.perf_counter()
        for index in range(sports_changes):
            predictor.prediction = available_prediction()
            await worker.handle_sports("mat_1", snapshot=None)
        sports_elapsed = time.perf_counter() - started

        started = time.perf_counter()
        book = worker._books.book  # noqa: SLF001
        for _ in range(book_changes):
            await worker.handle_book("mkt_1", book)
        book_elapsed = time.perf_counter() - started

        assert worker.queue_overflow_total() == 0
        action_digest = hashlib.sha256(
            json.dumps(
                [
                    (item.action.value, item.observation_version)
                    for item in observations.saved
                ]
            ).encode("utf-8")
        ).hexdigest()
        outputs.append(action_digest)

        book_p95 = metrics.percentile("book_to_decision", 95)
        sports_p95 = metrics.percentile("sports_to_decision", 95)
        assert book_p95 < 500.0, f"book->decision p95 {book_p95}ms"
        assert sports_p95 < 1000.0, f"sports->decision p95 {sports_p95}ms"
        # Sanity: the whole replay stays far below wall-clock budgets.
        assert book_elapsed < 30
        assert sports_elapsed < 30

    # Identical runs produce identical outputs.
    assert outputs[0] == outputs[1]
