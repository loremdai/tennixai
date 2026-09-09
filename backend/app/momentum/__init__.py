"""Recent Control Index v1: versioned calibration and the runtime engine."""

from .engine import ALGORITHM_VERSION, RecentControlEngine, recompute_observations

__all__ = [
    "ALGORITHM_VERSION",
    "Calibration",
    "CohortPrior",
    "RecentControlEngine",
    "load_calibration",
    "recompute_observations",
]


def __getattr__(name: str):
    """Keep calibration CLI modules lazy so ``python -m`` stays warning-free."""
    if name in {"Calibration", "CohortPrior", "load_calibration"}:
        from .calibration import Calibration, CohortPrior, load_calibration

        return {
            "Calibration": Calibration,
            "CohortPrior": CohortPrior,
            "load_calibration": load_calibration,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
