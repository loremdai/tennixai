"""The empty-opportunities aggregate reason (spec §6.2, T89).

Pure truth table: the reason and the model status a page shows must follow
the spec's precedence exactly, and a model state nobody confirmed may never
be reported as `not_promoted`.
"""

import pytest

from app.service import opportunity_reason


def _reason(**overrides):
    inputs = {
        "has_rows": False,
        "unpromoted_evidence": False,
        "covered": True,
        "unpromoted_deployment": False,
        "all_gapped": False,
        "promoted_evidence": False,
    }
    inputs.update(overrides)
    return opportunity_reason(**inputs)


def test_a_real_action_always_wins():
    assert _reason(has_rows=True) == ("HAS_OPPORTUNITIES", "unknown")
    assert _reason(has_rows=True, unpromoted_deployment=True)[0] == (
        "HAS_OPPORTUNITIES"
    )


def test_an_unpromoted_model_explains_the_empty_tab():
    # Evidence from a real observation…
    assert _reason(unpromoted_evidence=True) == (
        "ELIGIBLE_UNPROMOTED",
        "not_promoted",
    )
    # …and a deployment whose artifact is not promoted, even before anything
    # was evaluated: the tab must not claim the model ran and found nothing.
    assert _reason(unpromoted_deployment=True) == (
        "ELIGIBLE_UNPROMOTED",
        "not_promoted",
    )


def test_an_unpromoted_model_outranks_a_decision_gap():
    assert _reason(all_gapped=True, unpromoted_deployment=True) == (
        "ELIGIBLE_UNPROMOTED",
        "not_promoted",
    )


def test_a_promoted_model_never_claims_the_unpromoted_state():
    assert _reason(unpromoted_deployment=False) == ("NO_ELIGIBLE_ACTION", "unknown")
    assert _reason(promoted_evidence=True) == ("NO_ELIGIBLE_ACTION", "promoted")


def test_recovering_decisions_and_empty_domain_are_named_directly():
    assert _reason(all_gapped=True) == ("DECISION_GAP", "unknown")
    assert _reason(covered=False) == ("NO_COVERED_MARKET", "unknown")
    # No covered market means the deployment's model state is irrelevant.
    assert _reason(covered=False, unpromoted_deployment=True) == (
        "NO_COVERED_MARKET",
        "unknown",
    )


@pytest.mark.parametrize("promoted_evidence", [True, False])
def test_every_reason_is_a_documented_code(promoted_evidence: bool):
    reason, model_status = _reason(promoted_evidence=promoted_evidence)
    assert reason in {
        "HAS_OPPORTUNITIES",
        "ELIGIBLE_UNPROMOTED",
        "NO_ELIGIBLE_ACTION",
        "NO_COVERED_MARKET",
        "DECISION_GAP",
    }
    assert model_status in {"unknown", "promoted", "not_promoted"}
