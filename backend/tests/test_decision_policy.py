"""Versioned decision policy artifact tests (T63).

A policy that cannot prove validation+shadow selection with a positive
conservative net-EV lower bound disables BUY/SELL entirely; hash mismatch
fails closed.
"""

import hashlib
import json
from pathlib import Path

import pytest

from app.decision.policy import PolicyArtifact, PolicyRejected

FIXTURE = Path(__file__).parent / "fixtures" / "decision" / "policy-v1.json"


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_valid_policy_loads_versioned_thresholds():
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    policy = PolicyArtifact.load(FIXTURE, expected_sha256=digest)

    assert policy.policy_version == "policy-v1"
    assert policy.buy_min_conservative_net_edge == pytest.approx(0.03)
    assert policy.buy_min_model_probability_gap == pytest.approx(0.04)
    assert policy.sell_min_exit_net_edge == pytest.approx(0.02)
    assert policy.net_ev_lower_bound == pytest.approx(0.012)


def test_hash_mismatch_fails_closed(tmp_path):
    path = _write(tmp_path, _fixture_payload())

    with pytest.raises(PolicyRejected) as error:
        PolicyArtifact.load(path, expected_sha256="0" * 64)
    assert error.value.reason_code == "POLICY_HASH_MISMATCH"


def test_threshold_selected_on_test_set_is_rejected(tmp_path):
    payload = _fixture_payload()
    payload["threshold_selection"]["dataset"] = "test"
    path = _write(tmp_path, payload)

    with pytest.raises(PolicyRejected) as error:
        PolicyArtifact.load(path)
    assert error.value.reason_code == "THRESHOLD_SELECTED_ON_TEST"


def test_missing_shadow_replay_flag_is_rejected(tmp_path):
    payload = _fixture_payload()
    payload["threshold_selection"]["shadow_order_book_replay"] = False
    path = _write(tmp_path, payload)

    with pytest.raises(PolicyRejected) as error:
        PolicyArtifact.load(path)
    assert error.value.reason_code == "MISSING_SHADOW_EVIDENCE"


def test_missing_validation_or_shadow_evidence_is_rejected(tmp_path):
    for key in ("validation", "shadow"):
        payload = _fixture_payload()
        del payload["evidence"][key]
        path = _write(tmp_path, payload)

        with pytest.raises(PolicyRejected) as error:
            PolicyArtifact.load(path)
        assert error.value.reason_code == "MISSING_VALIDATION_SHADOW_EVIDENCE"


def test_non_positive_net_ev_lower_bound_disables_trading(tmp_path):
    payload = _fixture_payload()
    payload["net_ev_lower_bound"] = "0"
    path = _write(tmp_path, payload)

    with pytest.raises(PolicyRejected) as error:
        PolicyArtifact.load(path)
    assert error.value.reason_code == "NON_POSITIVE_NET_EV_LOWER_BOUND"


def test_malformed_policy_is_rejected(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(PolicyRejected) as error:
        PolicyArtifact.load(path)
    assert error.value.reason_code == "POLICY_UNREADABLE"
