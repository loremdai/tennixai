"""Deterministic contract tests for the P4.1 runtime persistence (T74).

Migration metadata, pure status/key guards and runtime payload models only;
behavior against a real PostgreSQL runs in tests/integration under the
`infrastructure` marker.
"""

import importlib.util
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain import MatchStatus
from app.persistence.repositories import (
    UnknownRuntimeStateKeyError,
    is_match_status_regression,
    require_runtime_state_key,
)
from app.runtime.models import (
    RuntimeHealth,
    RuntimeInitRecord,
    RuntimeSourceHealth,
    RuntimeSourceStatus,
)

FIXED_NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
NAIVE_NOW = datetime(2026, 9, 17, 10, 0)
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260917_0005_local_runtime_state.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_0005", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0005_chains_from_0004() -> None:
    module = _load_migration_module()
    assert module.revision == "0005"
    assert module.down_revision == "0004"


def test_migration_0005_touches_only_runtime_state() -> None:
    source = inspect.getsource(_load_migration_module())
    operations = re.findall(r"op\.(\w+)\(\s*\"([^\"]+)\"", source)
    assert operations, "migration must declare its operations"
    assert {table for _, table in operations} == {"runtime_state"}
    assert {operation for operation, _ in operations} <= {"create_table", "drop_table"}


def test_runtime_state_key_guard_accepts_only_the_local_runtime_pair() -> None:
    assert require_runtime_state_key("local_runtime_init") == "local_runtime_init"
    assert require_runtime_state_key("local_runtime_health") == "local_runtime_health"
    for key in ("", "init", "runtime_init", "local_runtime_raw", "provider_events"):
        with pytest.raises(UnknownRuntimeStateKeyError):
            require_runtime_state_key(key)


@pytest.mark.parametrize(
    ("existing", "incoming", "expected"),
    [
        (None, MatchStatus.SCHEDULED, False),
        (MatchStatus.SCHEDULED, MatchStatus.SCHEDULED, False),
        (MatchStatus.SCHEDULED, MatchStatus.LIVE, False),
        (MatchStatus.LIVE, MatchStatus.FINISHED, False),
        (MatchStatus.FINISHED, MatchStatus.FINISHED, False),
        (MatchStatus.POSTPONED, MatchStatus.SCHEDULED, False),
        (MatchStatus.LIVE, MatchStatus.SCHEDULED, True),
        (MatchStatus.FINISHED, MatchStatus.SCHEDULED, True),
        (MatchStatus.FINISHED, MatchStatus.LIVE, True),
        (MatchStatus.CANCELLED, MatchStatus.SCHEDULED, True),
    ],
)
def test_status_regression_guard_is_forward_only(
    existing: MatchStatus | None, incoming: MatchStatus, expected: bool
) -> None:
    assert is_match_status_regression(existing, incoming) is expected


def test_init_record_round_trips_through_json_payload() -> None:
    record = RuntimeInitRecord(
        completed_at=FIXED_NOW,
        migration_revision="0005",
        player_count=12,
        match_count=7,
    )
    payload = record.model_dump(mode="json")
    assert payload["migration_revision"] == "0005"
    assert payload["completed_at"] == "2026-09-17T10:00:00Z"
    assert RuntimeInitRecord.model_validate(payload) == record


def test_init_record_defaults_counts_to_zero() -> None:
    record = RuntimeInitRecord(completed_at=FIXED_NOW, migration_revision="0005")
    assert record.player_count == 0
    assert record.match_count == 0


def test_init_record_rejects_naive_datetimes_extra_fields_and_negative_counts() -> None:
    with pytest.raises(ValidationError):
        RuntimeInitRecord(completed_at=NAIVE_NOW, migration_revision="0005")
    with pytest.raises(ValidationError):
        RuntimeInitRecord(
            completed_at=FIXED_NOW, migration_revision="0005", external_match_id="123"
        )
    with pytest.raises(ValidationError):
        RuntimeInitRecord(
            completed_at=FIXED_NOW, migration_revision="0005", player_count=-1
        )


def test_init_record_is_frozen() -> None:
    record = RuntimeInitRecord(completed_at=FIXED_NOW, migration_revision="0005")
    with pytest.raises(ValidationError):
        record.migration_revision = "0004"


def test_health_round_trips_through_json_payload() -> None:
    health = RuntimeHealth(
        generated_at=FIXED_NOW,
        sources={
            "live_catalog": RuntimeSourceHealth(
                status=RuntimeSourceStatus.OK,
                last_success_at=FIXED_NOW,
                success_count=3,
            ),
            "market_discovery": RuntimeSourceHealth(
                status=RuntimeSourceStatus.UNAVAILABLE,
                reason_code="SOURCE_OFFLINE",
                failure_count=2,
            ),
        },
    )
    payload = health.model_dump(mode="json")
    assert payload["sources"]["market_discovery"]["reason_code"] == "SOURCE_OFFLINE"
    assert RuntimeHealth.model_validate(payload) == health


def test_health_defaults_to_no_sources() -> None:
    health = RuntimeHealth(generated_at=FIXED_NOW)
    assert health.sources == {}
    assert RuntimeHealth.model_validate(health.model_dump(mode="json")) == health


def test_health_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError):
        RuntimeHealth(generated_at=NAIVE_NOW)
    with pytest.raises(ValidationError):
        RuntimeSourceHealth(status=RuntimeSourceStatus.OK, last_success_at=NAIVE_NOW)


def test_health_gap_status_and_t78_fields_round_trip() -> None:
    health = RuntimeHealth(
        generated_at=FIXED_NOW,
        sources={
            "polymarket": RuntimeSourceHealth(
                status=RuntimeSourceStatus.GAP,
                reason_code="CONNECTION_LOST",
                last_event_at=FIXED_NOW,
                failure_count=1,
            ),
            "tennis_live": RuntimeSourceHealth(
                status=RuntimeSourceStatus.OK,
                last_success_at=FIXED_NOW,
                last_tracked=4,
                success_count=2,
            ),
        },
        counters={"decision_suppressed": 1, "realtime_callback_failures": 0},
        paper_status="paper_only",
        model_status="not_promoted",
    )
    payload = health.model_dump(mode="json")
    assert payload["sources"]["polymarket"]["status"] == "gap"
    assert payload["sources"]["tennis_live"]["last_tracked"] == 4
    assert payload["counters"]["decision_suppressed"] == 1
    assert RuntimeHealth.model_validate(payload) == health


def test_health_extended_fields_keep_legacy_payloads_valid() -> None:
    legacy = {
        "generated_at": FIXED_NOW.isoformat(),
        "sources": {
            "catalog": {
                "status": "ok",
                "reason_code": None,
                "last_success_at": FIXED_NOW.isoformat(),
                "success_count": 1,
                "failure_count": 0,
            }
        },
    }
    health = RuntimeHealth.model_validate(legacy)
    assert health.counters == {}
    assert health.paper_status is None
    assert health.model_status is None
    source = health.sources["catalog"]
    assert source.last_event_at is None
    assert source.last_tracked == 0


def test_health_rejects_naive_last_event_timestamps() -> None:
    with pytest.raises(ValidationError):
        RuntimeSourceHealth(status=RuntimeSourceStatus.OK, last_event_at=NAIVE_NOW)
