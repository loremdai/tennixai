"""Chronological walk-forward benchmark, artifacts and model card (T61).

Selection happens on validation only; the untouched out-of-time test split
is opened exactly once, after model and calibrator are frozen. Artifacts
carry SHA-256 hashes in a manifest, and the model card records provenance
and promotion without any raw row.
"""

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from app.prediction.audit import AuditReport, audit_source
from app.prediction.calibration import (
    brier_score,
    expected_calibration_error,
    log_loss_score,
    select_calibrator,
)
from app.prediction.data import (
    HistoricalMatch,
    HistoricalMatchSource,
    chronological_split,
)
from app.prediction.prematch import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    HgbmCandidate,
    PREMATCH_CANDIDATES,
)

BASELINE_LOG_LOSS = 0.6931471805599453  # constant p=0.5


class BenchmarkGateError(Exception):
    """Audit/license/leakage gate blocked the benchmark before training."""


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    reasons: tuple[str, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _outcomes(matches: Sequence[HistoricalMatch]) -> list[int]:
    return [1 if match.winner == "a" else 0 for match in matches]


def _per_match_losses(probs: Sequence[float], outcomes: Sequence[int]) -> list[float]:
    import math

    losses = []
    for probability, outcome in zip(probs, outcomes, strict=True):
        clipped = min(max(float(probability), 1e-6), 1 - 1e-6)
        losses.append(-math.log(clipped) if outcome else -math.log(1 - clipped))
    return losses


def match_bootstrap_ci(
    losses: Sequence[float], *, seed: int, draws: int = 1000
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    array = np.asarray(losses, dtype=float)
    if array.size == 0:
        return (float("nan"), float("nan"))
    means = [
        float(array[rng.integers(0, array.size, size=array.size)].mean())
        for _ in range(draws)
    ]
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def _accuracy(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    hits = sum(
        1
        for probability, outcome in zip(probs, outcomes, strict=True)
        if (probability >= 0.5) == bool(outcome)
    )
    return hits / len(probs)


def _subgroup_metrics(
    matches: Sequence[HistoricalMatch], probs: Sequence[float], outcomes: Sequence[int]
) -> dict[str, dict[str, dict[str, float]]]:
    groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for index, match in enumerate(matches):
        groups["tour"][match.tour].append(index)
        groups["surface"][match.surface].append(index)
        groups["format"][match.format].append(index)
    result: dict[str, dict[str, dict[str, float]]] = {}
    for dimension, buckets in groups.items():
        result[dimension] = {
            bucket: {
                "log_loss": log_loss_score(
                    [probs[i] for i in indices], [outcomes[i] for i in indices]
                ),
                "n": float(len(indices)),
            }
            for bucket, indices in sorted(buckets.items())
        }
    return result


def run_benchmark(
    source: HistoricalMatchSource,
    *,
    output_dir: Path,
    seed: int,
    code_version: str,
    today: date | None = None,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_report: AuditReport = audit_source(source, today=today)
    (output_dir / "audit.json").write_text(audit_report.to_json(), encoding="utf-8")
    if not audit_report.passed:
        raise BenchmarkGateError(
            f"data audit failed: {'; '.join(audit_report.reasons)}"
        )

    matches = source.load()
    splits = chronological_split(matches)
    ordered = sorted(matches, key=lambda item: (item.date, item.match_key))
    position = {match.match_key: index for index, match in enumerate(ordered)}
    val_indices = [position[match.match_key] for match in splits.validation]
    test_indices = [position[match.match_key] for match in splits.test]
    val_outcomes = _outcomes(splits.validation)
    test_outcomes = _outcomes(splits.test)

    # --- candidates: fit on train, compare on validation only ---
    results: dict[str, dict] = {}
    for klass in PREMATCH_CANDIDATES:
        candidate = klass(seed=seed) if klass is HgbmCandidate else klass()
        state = candidate.fit(splits.train)
        val_probs = candidate.predict_sequence(state, ordered, val_indices)
        clipped = [min(max(value, 1e-6), 1 - 1e-6) for value in val_probs]
        losses = _per_match_losses(clipped, val_outcomes)
        low, high = match_bootstrap_ci(losses, seed=seed)
        results[candidate.name] = {
            "candidate": candidate,
            "state": state,
            "val_probs": clipped,
            "log_loss": log_loss_score(clipped, val_outcomes),
            "ci": (low, high),
            "complexity_rank": candidate.complexity_rank,
        }

    best = min(results.values(), key=lambda item: item["log_loss"])
    tie_margin = (best["ci"][1] - best["ci"][0]) / 2
    tied = [
        entry
        for entry in results.values()
        if entry["log_loss"] <= best["log_loss"] + tie_margin
    ]
    champion_entry = min(tied, key=lambda item: item["complexity_rank"])
    champion = champion_entry["candidate"]

    # --- calibrator: validation only ---
    calibrator, calibration_report = select_calibrator(
        champion_entry["val_probs"], val_outcomes, seed=seed
    )

    # --- untouched test: opened exactly once, after selection ---
    test_probs_raw = champion.predict_sequence(
        champion_entry["state"], ordered, test_indices
    )
    test_probs = [
        float(value)
        for value in np.clip(
            calibrator.predict(
                [min(max(value, 1e-6), 1 - 1e-6) for value in test_probs_raw]
            ),
            1e-6,
            1 - 1e-6,
        )
    ]
    test_losses = _per_match_losses(test_probs, test_outcomes)
    test_low, test_high = match_bootstrap_ci(test_losses, seed=seed)
    test_metrics = {
        "log_loss": log_loss_score(test_probs, test_outcomes),
        "brier": brier_score(test_probs, test_outcomes),
        "ece": expected_calibration_error(test_probs, test_outcomes),
        "accuracy": _accuracy(test_probs, test_outcomes),
        "ci95_log_loss": [test_low, test_high],
        "n": len(test_probs),
    }
    test_matches = [ordered[index] for index in test_indices]
    subgroups = _subgroup_metrics(test_matches, test_probs, test_outcomes)

    # Pre-declared promotion rule: the conservative (upper) CI bound of the
    # test log loss must beat the constant-0.5 baseline. No threshold may be
    # re-chosen after seeing the test split.
    promoted = test_high < BASELINE_LOG_LOSS
    promotion = {
        "result": "promoted" if promoted else "not_promoted",
        "rule": "test log-loss CI95 upper bound < ln(2) baseline",
        "decision_layer_note": (
            "model promotion does not authorize BUY/SELL; decision thresholds "
            "require separate validation+shadow evidence (T63/T71)"
        ),
    }

    def window(rows: Sequence[HistoricalMatch]) -> tuple[str, str]:
        return (rows[0].date.isoformat(), rows[-1].date.isoformat())

    windows = {
        "train": window(splits.train),
        "validation": window(splits.validation),
        "test": window(splits.test),
    }

    # --- artifacts ---
    champion.save(output_dir, champion_entry["state"])
    calibrator.save(output_dir / "calibrator.joblib")
    feature_schema = {
        "version": FEATURE_SCHEMA_VERSION,
        "features": list(FEATURE_NAMES),
        "champion": champion.name,
        "champion_version": champion.version,
        "calibrator": calibrator.name,
        "seed": seed,
    }
    (output_dir / "feature-schema.json").write_text(
        json.dumps(feature_schema, indent=2, sort_keys=True), encoding="utf-8"
    )

    model_card = {
        "card_version": "p3-model-card-v1",
        "source_id": audit_report.source_id,
        "license_id": audit_report.license_id,
        "code_version": code_version,
        "seed": seed,
        "windows": windows,
        "champion": {
            "name": champion.name,
            "version": champion.version,
            "complexity_rank": champion.complexity_rank,
        },
        "validation": {
            "log_loss": {
                name: entry["log_loss"] for name, entry in sorted(results.items())
            },
            "tie_margin": tie_margin,
        },
        "calibration": {
            "selected": calibration_report["selected"],
            "tie_within_ci": calibration_report["tie_within_ci"],
            "candidates": calibration_report["candidates"],
        },
        "metrics": test_metrics,
        "subgroups": subgroups,
        "promotion": promotion,
    }
    (output_dir / "model-card.json").write_text(
        json.dumps(model_card, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    report_payload = {
        "audit": json.loads(audit_report.to_json()),
        "selection": {
            "dataset": "validation",
            "champion": champion.name,
            "tie_margin": tie_margin,
            "candidates": {
                name: {"log_loss": entry["log_loss"], "ci": list(entry["ci"])}
                for name, entry in sorted(results.items())
            },
        },
        "test_opened": True,
        "test_metrics": test_metrics,
        "subgroups": subgroups,
        "windows": windows,
        "promotion": promotion,
    }
    (output_dir / "benchmark-report.json").write_text(
        json.dumps(report_payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    artifact_names = [
        "model.joblib",
        "calibrator.joblib",
        "feature-schema.json",
        "model-card.json",
        "audit.json",
        "benchmark-report.json",
    ]
    manifest = {
        "manifest_version": "p3-manifest-v1",
        "code_version": code_version,
        "seed": seed,
        "files": {
            name: {
                "sha256": _sha256(output_dir / name),
                "bytes": (output_dir / name).stat().st_size,
            }
            for name in artifact_names
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    return report_payload


REQUIRED_CARD_FIELDS = (
    "source_id",
    "license_id",
    "code_version",
    "windows",
    "champion",
    "calibration",
    "metrics",
    "subgroups",
    "promotion",
)


def verify_artifact(artifact_dir: Path | str) -> VerifyResult:
    directory = Path(artifact_dir)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return VerifyResult(ok=False, reasons=("manifest.json missing",))
    reasons: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError:
        return VerifyResult(ok=False, reasons=("manifest.json invalid",))
    for name, entry in manifest.get("files", {}).items():
        path = directory / name
        if not path.is_file():
            reasons.append(f"{name}: file missing")
            continue
        digest = _sha256(path)
        if digest != entry.get("sha256"):
            reasons.append(f"{name}: sha256 mismatch")
    card_path = directory / "model-card.json"
    if not card_path.is_file():
        reasons.append("model-card.json missing")
    else:
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except ValueError:
            reasons.append("model-card.json invalid")
        else:
            for field_name in REQUIRED_CARD_FIELDS:
                if card.get(field_name) in (None, "", {}):
                    reasons.append(f"model-card.json missing field: {field_name}")
    return VerifyResult(ok=not reasons, reasons=tuple(reasons))
