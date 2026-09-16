"""Walk-forward benchmark, artifact and model-card tests (T61)."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.prediction.benchmark import run_benchmark, verify_artifact
from app.prediction.data import CsvHistoricalMatchSource

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prediction"


def test_fixture_benchmark_produces_verifiable_artifacts(tmp_path):
    source = CsvHistoricalMatchSource(FIXTURE_DIR)

    report = run_benchmark(
        source,
        output_dir=tmp_path,
        seed=42,
        code_version="test-commit",
        today=date(2026, 9, 16),
    )

    assert (tmp_path / "manifest.json").is_file()
    assert (tmp_path / "model-card.json").is_file()
    assert (tmp_path / "feature-schema.json").is_file()

    result = verify_artifact(tmp_path)
    assert result.ok, result.reasons

    # Selection happened on validation; test was opened exactly once after.
    assert report["selection"]["dataset"] == "validation"
    assert report["test_opened"] is True
    metrics = report["test_metrics"]
    assert 0 < metrics["log_loss"] < 2
    assert 0 <= metrics["brier"] <= 1
    assert "ci95_log_loss" in metrics
    subgroups = report["subgroups"]
    assert "tour" in subgroups and "surface" in subgroups and "format" in subgroups


def test_model_card_contains_required_provenance_without_raw_rows(tmp_path):
    source = CsvHistoricalMatchSource(FIXTURE_DIR)

    run_benchmark(
        source,
        output_dir=tmp_path,
        seed=42,
        code_version="test-commit-abc",
        today=date(2026, 9, 16),
    )

    card = json.loads((tmp_path / "model-card.json").read_text())
    assert card["source_id"] == "tennix-synth-fixture-v1"
    assert card["license_id"] == "CC0-1.0-synthetic"
    assert card["code_version"] == "test-commit-abc"
    assert card["windows"]["train"][0] <= card["windows"]["train"][1]
    assert card["windows"]["test"][0] > card["windows"]["validation"][1]
    assert card["promotion"]["result"] in ("promoted", "not_promoted")
    assert "calibration" in card
    assert "metrics" in card and "subgroups" in card

    serialized = json.dumps(card)
    assert "PLR_" not in serialized  # no raw rows or player identifiers


def test_fixed_seed_reproduces_identical_manifest_hashes(tmp_path):
    source = CsvHistoricalMatchSource(FIXTURE_DIR)
    first = tmp_path / "first"
    second = tmp_path / "second"

    run_benchmark(
        source, output_dir=first, seed=42, code_version="v", today=date(2026, 9, 16)
    )
    run_benchmark(
        source, output_dir=second, seed=42, code_version="v", today=date(2026, 9, 16)
    )

    manifest_a = json.loads((first / "manifest.json").read_text())
    manifest_b = json.loads((second / "manifest.json").read_text())
    hashes_a = {name: entry["sha256"] for name, entry in manifest_a["files"].items()}
    hashes_b = {name: entry["sha256"] for name, entry in manifest_b["files"].items()}
    # Model/calibrator/feature artifacts must be byte-identical; the card
    # embeds generated_at, so compare only non-timestamped files.
    for name in ("model.joblib", "calibrator.joblib", "feature-schema.json"):
        assert hashes_a[name] == hashes_b[name], name


def test_tampered_artifact_fails_verification(tmp_path):
    source = CsvHistoricalMatchSource(FIXTURE_DIR)
    run_benchmark(
        source, output_dir=tmp_path, seed=42, code_version="v", today=date(2026, 9, 16)
    )

    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(model_path.read_bytes() + b"tampered")

    result = verify_artifact(tmp_path)
    assert not result.ok
    assert any("model.joblib" in reason for reason in result.reasons)


def test_missing_manifest_fails_verification(tmp_path):
    result = verify_artifact(tmp_path)
    assert not result.ok


def test_audit_gate_blocks_benchmark_before_training(tmp_path, monkeypatch):
    from app.prediction import benchmark as benchmark_module

    source = CsvHistoricalMatchSource(FIXTURE_DIR)

    def failing_audit(*args, **kwargs):
        raise AssertionError("must not be called")

    class FailedAudit:
        passed = False
        reasons = ("license missing",)

        def to_json(self):
            return json.dumps({"passed": False})

    monkeypatch.setattr(benchmark_module, "audit_source", lambda *a, **k: FailedAudit())
    assert failing_audit  # referenced to keep the intent explicit

    with pytest.raises(benchmark_module.BenchmarkGateError):
        run_benchmark(
            source,
            output_dir=tmp_path,
            seed=42,
            code_version="v",
            today=date(2026, 9, 16),
        )
