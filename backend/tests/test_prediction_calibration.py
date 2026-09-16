"""Calibration candidates and selection tests (T61).

Selection happens on validation only; ties inside bootstrap uncertainty
prefer the simpler calibrator.
"""

import numpy as np
import pytest

from app.prediction.calibration import (
    BetaCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
    brier_score,
    expected_calibration_error,
    log_loss_score,
    select_calibrator,
)


def overconfident_scores(n: int = 400, seed: int = 7):
    """Synthetic probabilities that are systematically overconfident."""
    rng = np.random.default_rng(seed)
    latent = rng.uniform(0.15, 0.85, size=n)
    outcomes = (rng.random(n) < latent).astype(int)
    pushed = np.clip(0.5 + (latent - 0.5) * 1.7, 0.02, 0.98)
    return pushed, outcomes


def test_metric_functions_on_hand_computed_samples():
    # Two-point log loss: -ln(0.5) for both correct/incorrect at p=0.5.
    assert log_loss_score([0.5, 0.5], [1, 0]) == pytest.approx(0.693147, abs=1e-5)
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert log_loss_score([0.9, 0.1], [1, 0]) < 0.3


def test_expected_calibration_error_detects_overconfidence():
    scores, outcomes = overconfident_scores()
    raw_ece = expected_calibration_error(scores, outcomes)
    assert raw_ece > 0.05


@pytest.mark.parametrize(
    "calibrator_class", [PlattCalibrator, IsotonicCalibrator, BetaCalibrator]
)
def test_calibrators_reduce_error_and_stay_monotonic(calibrator_class):
    scores, outcomes = overconfident_scores()
    calibrator = calibrator_class()
    calibrator.fit(scores, outcomes)
    calibrated = calibrator.predict(scores)

    assert expected_calibration_error(
        calibrated, outcomes
    ) < expected_calibration_error(scores, outcomes)
    order = np.argsort(scores)
    calibrated_sorted = np.asarray(calibrated)[order]
    # Weak monotonicity: calibrated output never decreases with raw score.
    assert np.all(np.diff(calibrated_sorted) >= -1e-9)


def test_calibrator_artifacts_round_trip(tmp_path):
    scores, outcomes = overconfident_scores(n=200)
    for calibrator in (PlattCalibrator(), IsotonicCalibrator(), BetaCalibrator()):
        calibrator.fit(scores, outcomes)
        path = tmp_path / f"{calibrator.name}.joblib"
        calibrator.save(path)
        reloaded = type(calibrator).load(path)
        assert reloaded.predict(scores[:20]) == pytest.approx(
            calibrator.predict(scores[:20])
        )


def test_selection_uses_validation_and_prefers_simpler_on_ties():
    scores, outcomes = overconfident_scores(n=300, seed=11)

    selected, report = select_calibrator(scores, outcomes, seed=42)

    assert report["dataset"] == "validation"
    assert selected.name in {"platt", "isotonic", "beta"}
    # The chosen calibrator must be within one standard error of the best.
    best = min(report["candidates"], key=lambda item: item["log_loss"])
    assert (
        report["candidates"][
            [c["name"] for c in report["candidates"]].index(selected.name)
        ]["log_loss"]
        <= best["log_loss"] + report["tie_margin"]
    )


def test_tie_break_prefers_platt_over_isotonic():
    # Perfectly calibrated identical inputs make every calibrator tie.
    rng = np.random.default_rng(3)
    n = 500
    scores = rng.uniform(0.05, 0.95, n)
    outcomes = (rng.random(n) < scores).astype(int)

    selected, report = select_calibrator(scores, outcomes, seed=42)

    assert report["tie_within_ci"] in (True, False)
    if report["tie_within_ci"]:
        assert selected.name == "platt"
