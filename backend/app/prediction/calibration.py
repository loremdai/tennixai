"""Calibration candidates, metrics and validation-only selection (T61).

Platt/logistic, isotonic and beta calibration are compared on validation
data only; the untouched test split never participates in selection. Ties
inside bootstrap uncertainty prefer the simpler calibrator.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

CLIP = 1e-6


def log_loss_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    total = 0.0
    for probability, outcome in zip(probs, outcomes, strict=True):
        clipped = min(max(float(probability), CLIP), 1.0 - CLIP)
        total += -math.log(clipped) if outcome else -math.log(1.0 - clipped)
    return total / len(probs)


def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    return float(
        np.mean(
            [
                (float(probability) - float(outcome)) ** 2
                for probability, outcome in zip(probs, outcomes, strict=True)
            ]
        )
    )


def reliability_curve(
    probs: Sequence[float], outcomes: Sequence[int], bins: int = 10
) -> list[tuple[float, float, int]]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    curve: list[tuple[float, float, int]] = []
    probabilities = np.asarray(probs, dtype=float)
    labels = np.asarray(outcomes, dtype=float)
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= low) & (probabilities <= high)
        else:
            mask = (probabilities >= low) & (probabilities < high)
        count = int(mask.sum())
        if count == 0:
            continue
        curve.append(
            (float(probabilities[mask].mean()), float(labels[mask].mean()), count)
        )
    return curve


def expected_calibration_error(
    probs: Sequence[float], outcomes: Sequence[int], bins: int = 10
) -> float:
    total = len(probs)
    if total == 0:
        return 0.0
    error = 0.0
    for predicted, observed, count in reliability_curve(probs, outcomes, bins):
        error += count / total * abs(predicted - observed)
    return error


@dataclass(frozen=True)
class CalibrationSelection:
    name: str
    log_loss: float
    ece: float
    tie_within_ci: bool


class BaseCalibrator:
    name = "base"
    complexity_rank = 0

    def fit(self, probs: Sequence[float], outcomes: Sequence[int]) -> None:
        raise NotImplementedError

    def predict(self, probs: Sequence[float]) -> np.ndarray:
        raise NotImplementedError

    def save(self, path: Path) -> None:
        joblib.dump({"kind": self.name, "state": self.__dict__}, path)

    @classmethod
    def load(cls, path: Path) -> "BaseCalibrator":
        payload = joblib.load(path)
        instance = cls()
        instance.__dict__.update(payload["state"])
        return instance


class PlattCalibrator(BaseCalibrator):
    name = "platt"
    complexity_rank = 1

    def fit(self, probs: Sequence[float], outcomes: Sequence[int]) -> None:
        from sklearn.linear_model import LogisticRegression

        probabilities = np.clip(np.asarray(probs, dtype=float), CLIP, 1 - CLIP)
        logits = np.log(probabilities / (1 - probabilities)).reshape(-1, 1)
        self._model = LogisticRegression(C=1e6, max_iter=1000)
        self._model.fit(logits, np.asarray(outcomes, dtype=int))

    def predict(self, probs: Sequence[float]) -> np.ndarray:
        probabilities = np.clip(np.asarray(probs, dtype=float), CLIP, 1 - CLIP)
        logits = np.log(probabilities / (1 - probabilities)).reshape(-1, 1)
        return self._model.predict_proba(logits)[:, 1]


class BetaCalibrator(BaseCalibrator):
    """Two-parameter beta calibration via logistic regression on
    [log p, -log(1-p)] features."""

    name = "beta"
    complexity_rank = 2

    def fit(self, probs: Sequence[float], outcomes: Sequence[int]) -> None:
        from sklearn.linear_model import LogisticRegression

        probabilities = np.clip(np.asarray(probs, dtype=float), CLIP, 1 - CLIP)
        features = np.column_stack([np.log(probabilities), -np.log(1 - probabilities)])
        self._model = LogisticRegression(C=1e6, max_iter=1000)
        self._model.fit(features, np.asarray(outcomes, dtype=int))

    def predict(self, probs: Sequence[float]) -> np.ndarray:
        probabilities = np.clip(np.asarray(probs, dtype=float), CLIP, 1 - CLIP)
        features = np.column_stack([np.log(probabilities), -np.log(1 - probabilities)])
        return self._model.predict_proba(features)[:, 1]


class IsotonicCalibrator(BaseCalibrator):
    name = "isotonic"
    complexity_rank = 3

    def fit(self, probs: Sequence[float], outcomes: Sequence[int]) -> None:
        from sklearn.isotonic import IsotonicRegression

        self._model = IsotonicRegression(
            y_min=CLIP, y_max=1 - CLIP, out_of_bounds="clip"
        )
        self._model.fit(np.asarray(probs, dtype=float), np.asarray(outcomes, dtype=int))

    def predict(self, probs: Sequence[float]) -> np.ndarray:
        return np.asarray(
            self._model.predict(np.asarray(probs, dtype=float)), dtype=float
        )


CALIBRATOR_CLASSES = (PlattCalibrator, BetaCalibrator, IsotonicCalibrator)


def _bootstrap_log_losses(
    probs: Sequence[float], outcomes: Sequence[int], *, seed: int, draws: int = 200
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(probs)
    losses: dict[str, list[float]] = {}
    arrays = {name: None for name in ("platt", "beta", "isotonic")}
    fitted: dict[str, BaseCalibrator] = {}
    for klass in CALIBRATOR_CLASSES:
        calibrator = klass()
        calibrator.fit(probs, outcomes)
        fitted[klass.name] = calibrator
        arrays[klass.name] = np.asarray(calibrator.predict(probs), dtype=float)
    outcomes_array = np.asarray(outcomes, dtype=int)
    for _ in range(draws):
        sample = rng.integers(0, n, size=n)
        for name, calibrated in arrays.items():
            losses.setdefault(name, []).append(
                log_loss_score(calibrated[sample], outcomes_array[sample])
            )
    means = {name: float(np.mean(values)) for name, values in losses.items()}
    stds = {name: float(np.std(values)) for name, values in losses.items()}
    return means, stds  # type: ignore[return-value]


def select_calibrator(
    probs: Sequence[float],
    outcomes: Sequence[int],
    *,
    seed: int = 42,
    bins: int = 10,
) -> tuple[BaseCalibrator, dict]:
    """Select on validation data only; simpler wins inside the tie margin."""
    fitted: dict[str, BaseCalibrator] = {}
    candidates: list[dict] = []
    for klass in CALIBRATOR_CLASSES:
        calibrator = klass()
        calibrator.fit(probs, outcomes)
        fitted[klass.name] = calibrator
        calibrated = calibrator.predict(probs)
        candidates.append(
            {
                "name": klass.name,
                "complexity_rank": klass.complexity_rank,
                "log_loss": log_loss_score(list(calibrated), list(outcomes)),
                "brier": brier_score(list(calibrated), list(outcomes)),
                "ece": expected_calibration_error(
                    list(calibrated), list(outcomes), bins
                ),
            }
        )
    means, stds = _bootstrap_log_losses(probs, outcomes, seed=seed)
    tie_margin = float(np.mean(list(stds.values())))
    best = min(candidates, key=lambda item: item["log_loss"])
    tied = [
        candidate
        for candidate in candidates
        if candidate["log_loss"] <= best["log_loss"] + tie_margin
    ]
    chosen = min(tied, key=lambda item: item["complexity_rank"])
    selected = fitted[chosen["name"]]
    report = {
        "dataset": "validation",
        "candidates": candidates,
        "tie_margin": tie_margin,
        "tie_within_ci": chosen["name"] != best["name"],
        "bootstrap_means": {name: float(value) for name, value in means.items()},
        "selected": chosen["name"],
    }
    return selected, report
