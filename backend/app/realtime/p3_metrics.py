"""Low-cardinality P3 pipeline metrics (T65).

Stage histograms (ingress→canonical, canonical→prediction,
prediction/book→decision, ledger-commit→publish) plus backlog, reconnect
and gap counters. Labels are stage names only: player, match, market or
token identifiers never appear in metrics.
"""

import json
from collections import deque

STAGE_NAMES = frozenset(
    {
        "ingress_to_canonical",
        "canonical_to_prediction",
        "prediction_to_decision",
        "book_to_decision",
        "sports_to_decision",
        "ledger_commit_to_publish",
    }
)
COUNTER_NAMES = frozenset(
    {
        "queue_overflow",
        "backlog_dropped",
        "reconnects",
        "tracking_gaps",
        "decision_suppressed",
    }
)
MAX_SAMPLES = 100_000


class P3Metrics:
    def __init__(self) -> None:
        self._samples: dict[str, deque[float]] = {}
        self._counters: dict[str, int] = {}

    def observe(self, stage: str, milliseconds: float) -> None:
        bucket = self._samples.setdefault(stage, deque(maxlen=MAX_SAMPLES))
        bucket.append(float(milliseconds))

    def increment(self, counter: str) -> None:
        self._counters[counter] = self._counters.get(counter, 0) + 1

    def count(self, stage: str) -> int:
        return len(self._samples.get(stage, ()))

    def percentile(self, stage: str, percent: float) -> float:
        samples = sorted(self._samples.get(stage, ()))
        if not samples:
            return 0.0
        rank = max(1, int(-(-percent / 100 * len(samples) // 1)))
        return samples[min(rank, len(samples)) - 1]

    def export(self) -> str:
        stages = {
            stage: {
                "count": len(samples),
                "p50": self.percentile(stage, 50),
                "p95": self.percentile(stage, 95),
                "p99": self.percentile(stage, 99),
            }
            for stage, samples in sorted(self._samples.items())
        }
        return json.dumps(
            {"stages": stages, "counters": dict(sorted(self._counters.items()))},
            sort_keys=True,
        )
