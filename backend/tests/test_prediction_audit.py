"""P3 data license/coverage/leakage audit tests (T61)."""

import json
from datetime import date
from pathlib import Path


from app.prediction.audit import audit_source
from app.prediction.data import (
    CsvHistoricalMatchSource,
    HistoricalMatch,
    InMemoryHistoricalMatchSource,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prediction"


def test_fixture_audit_passes_with_coverage_facts():
    source = CsvHistoricalMatchSource(FIXTURE_DIR)

    report = audit_source(source, today=date(2026, 9, 16))

    assert report.passed
    assert report.source_id == "tennix-synth-fixture-v1"
    assert report.license_id == "CC0-1.0-synthetic"
    assert report.total_matches == 200
    assert report.date_range == ("2024-01-02", "2026-06-15") or (
        report.date_range[0] < report.date_range[1]
    )
    assert report.tour_counts.get("atp", 0) > 0
    assert report.tour_counts.get("wta", 0) > 0
    assert set(report.surface_counts) <= {"hard", "clay", "grass", "unknown"}
    assert report.format_counts.get("best_of_3", 0) > 0
    assert 0.0 <= report.player_cold_start_ratio <= 1.0
    assert report.duplicate_match_keys == 0
    assert report.future_dated_rows == 0
    assert report.forbidden_columns == ()


def test_audit_fails_without_license_identifier():
    day = date(2024, 1, 1)
    match = HistoricalMatch(
        match_key="m1",
        date=day,
        tour="atp",
        surface="hard",
        format="best_of_3",
        player_a="A",
        player_b="B",
        winner="a",
    )
    source = InMemoryHistoricalMatchSource((match,), source_id="s", license_id=None)

    report = audit_source(source, today=date(2026, 9, 16))

    assert not report.passed
    assert any("license" in reason.lower() for reason in report.reasons)


def test_audit_fails_on_empty_data():
    source = InMemoryHistoricalMatchSource((), source_id="s", license_id="l")

    report = audit_source(source, today=date(2026, 9, 16))

    assert not report.passed
    assert any("empty" in reason.lower() for reason in report.reasons)


def test_audit_report_is_serializable_and_carries_no_raw_rows():
    source = CsvHistoricalMatchSource(FIXTURE_DIR)

    report = audit_source(source, today=date(2026, 9, 16))
    payload = json.loads(report.to_json())

    serialized = json.dumps(payload)
    assert "PLR_" not in serialized  # aggregate facts only, no raw rows
    assert payload["passed"] is True
    assert payload["total_matches"] == 200
