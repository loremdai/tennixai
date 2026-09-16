"""One-shot FOK paper state machine transition-table tests (T64).

Pure in-memory validation: duplicate entry/exit, retries after
MISSED/EXIT_MISSED, partial fills, side switches, add-ons, out-of-order
transitions and mutation of frozen evidence are all rejected.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.paper.models import (
    IntentSide,
    PaperFill,
    PaperLifecycleState,
    PaperOrderIntent,
    TrackName,
)
from app.paper.state_machine import (
    MatchLedger,
    PaperStateMachine,
    PaperTransitionError,
    TransitionEvidence,
)
from p3_fakes import make_intent, make_track_result

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)

MACHINE = PaperStateMachine()


def evidence(rules_hash: str = "rules_v1") -> TransitionEvidence:
    return TransitionEvidence(
        prediction_version="prematch-elo-v1",
        decision_observation_version=3,
        rules_hash=rules_hash,
        fee_rate=Decimal("0.02"),
        delay_seconds=10,
        book_hash="book_v9",
    )


def entry_fill(intent_id: str, *, shares: str = "19.047619", price: str = "0.525"):
    return PaperFill(
        intent_id=intent_id,
        filled=True,
        shares=Decimal(shares),
        average_price=Decimal(price),
        fee=Decimal("0.05"),
        executed_book_hash="book_v10",
        executed_at=NOW + timedelta(seconds=15),
    )


def no_fill(intent_id: str, reason: str = "DEPTH_INSUFFICIENT") -> PaperFill:
    return PaperFill(
        intent_id=intent_id,
        filled=False,
        reason=reason,
        executed_book_hash="book_v10",
        executed_at=NOW + timedelta(seconds=15),
    )


def started_ledger() -> tuple[MatchLedger, PaperOrderIntent]:
    intent = make_intent("mat_1", "mkt_1")
    ledger = MatchLedger(match_id="mat_1", position_outcome="ply_a")
    return MACHINE.begin_entry(ledger, intent, evidence()), intent


def filled_ledger() -> tuple[MatchLedger, PaperOrderIntent]:
    ledger, intent = started_ledger()
    return (
        MACHINE.apply_entry_fill(
            ledger,
            entry_fill(intent.id),
            position_id="pos_1",
            entry_cost=Decimal("10.00"),
            shares=Decimal("19.047619"),
        ),
        intent,
    )


# ---------------------------------------------------------------------------
# Legal chains
# ---------------------------------------------------------------------------


def test_entry_chain_pending_to_filled():
    ledger, intent = started_ledger()
    assert ledger.lifecycle is PaperLifecycleState.ENTRY_PENDING

    ledger = MACHINE.apply_entry_fill(
        ledger,
        entry_fill(intent.id),
        position_id="pos_1",
        entry_cost=Decimal("10.00"),
        shares=Decimal("19.047619"),
    )
    assert ledger.lifecycle is PaperLifecycleState.FILLED
    assert ledger.position_id == "pos_1"


def test_entry_no_fill_is_terminal_missed():
    ledger, intent = started_ledger()

    ledger = MACHINE.apply_entry_fill(ledger, no_fill(intent.id))

    assert ledger.lifecycle is PaperLifecycleState.MISSED
    # MISSED is terminal: no retry, no exit, no settlement.
    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_entry(ledger, make_intent("mat_1", "mkt_1"), evidence())
    assert error.value.reason_code == "ENTRY_EXISTS"
    with pytest.raises(PaperTransitionError):
        MACHINE.apply_settlement(ledger, ())


def test_full_exit_chain_and_settlement():
    ledger, _ = filled_ledger()

    exit_intent = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v1"
    )
    ledger = MACHINE.begin_exit(ledger, exit_intent, evidence())
    assert ledger.lifecycle is PaperLifecycleState.EXIT_PENDING

    ledger = MACHINE.apply_exit_fill(
        ledger, entry_fill(exit_intent.id, shares="19.047619", price="0.65")
    )
    assert ledger.lifecycle is PaperLifecycleState.EXITED

    tracks = tuple(
        make_track_result("mat_1", "pos_1", track=track)
        for track in (
            TrackName.EV_EXIT,
            TrackName.HODL_BASELINE,
            TrackName.CONVERGENCE_LOCK,
        )
    )
    ledger = MACHINE.apply_settlement(ledger, tracks)
    assert ledger.lifecycle is PaperLifecycleState.SETTLED


def test_exit_no_fill_holds_to_settlement():
    ledger, _ = filled_ledger()
    exit_intent = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v1"
    )
    ledger = MACHINE.begin_exit(ledger, exit_intent, evidence())
    ledger = MACHINE.apply_exit_fill(ledger, no_fill(exit_intent.id))
    assert ledger.lifecycle is PaperLifecycleState.EXIT_MISSED

    # No second exit attempt ever.
    retry = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v2"
    )
    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_exit(ledger, retry, evidence())
    assert error.value.reason_code == "EXIT_EXISTS"

    tracks = tuple(
        make_track_result("mat_1", "pos_1", track=track)
        for track in (
            TrackName.EV_EXIT,
            TrackName.HODL_BASELINE,
            TrackName.CONVERGENCE_LOCK,
        )
    )
    ledger = MACHINE.apply_settlement(ledger, tracks)
    assert ledger.lifecycle is PaperLifecycleState.SETTLED


def test_filled_can_settle_directly_when_never_sold():
    ledger, _ = filled_ledger()
    tracks = tuple(
        make_track_result("mat_1", "pos_1", track=track)
        for track in (
            TrackName.EV_EXIT,
            TrackName.HODL_BASELINE,
            TrackName.CONVERGENCE_LOCK,
        )
    )
    ledger = MACHINE.apply_settlement(ledger, tracks)
    assert ledger.lifecycle is PaperLifecycleState.SETTLED


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def test_duplicate_entry_and_add_on_are_rejected():
    ledger, _ = started_ledger()
    second = make_intent("mat_1", "mkt_1", idempotency_key="entry:mat_1:v2")

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_entry(ledger, second, evidence())
    assert error.value.reason_code == "ENTRY_EXISTS"


def test_exit_before_fill_is_out_of_order():
    ledger = MatchLedger(match_id="mat_1", position_outcome="ply_a")
    exit_intent = make_intent("mat_1", "mkt_1", side=IntentSide.EXIT)

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_exit(ledger, exit_intent, evidence())
    assert error.value.reason_code == "EXIT_NOT_ALLOWED"


def test_duplicate_exit_is_rejected():
    ledger, _ = filled_ledger()
    first = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v1"
    )
    ledger = MACHINE.begin_exit(ledger, first, evidence())
    second = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v2"
    )

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_exit(ledger, second, evidence())
    assert error.value.reason_code == "EXIT_EXISTS"


def test_side_switch_exit_is_rejected():
    ledger, _ = filled_ledger()
    switched = make_intent(
        "mat_1",
        "mkt_1",
        side=IntentSide.EXIT,
        idempotency_key="exit:mat_1:v1",
    )
    switched = switched.model_copy(update={"outcome_player_id": "ply_b"})

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.begin_exit(ledger, switched, evidence())
    assert error.value.reason_code == "SIDE_SWITCH"


def test_partial_fill_is_rejected():
    ledger, intent = started_ledger()
    # $10 stake at 0.525 requires ~19.05 shares; 10 shares is a partial.
    partial = entry_fill(intent.id, shares="10", price="0.525")

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.apply_entry_fill(
            ledger,
            partial,
            position_id="pos_1",
            entry_cost=Decimal("5.25"),
            shares=Decimal("10"),
        )
    assert error.value.reason_code == "PARTIAL_FILL"


def test_frozen_evidence_mutation_is_rejected():
    ledger, _ = filled_ledger()
    exit_intent = make_intent(
        "mat_1", "mkt_1", side=IntentSide.EXIT, idempotency_key="exit:mat_1:v1"
    )
    ledger = MACHINE.begin_exit(ledger, exit_intent, evidence("rules_v1"))

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.apply_exit_fill(
            ledger,
            entry_fill(exit_intent.id, shares="19.047619", price="0.65"),
            evidence=evidence("rules_v2"),
        )
    assert error.value.reason_code == "EVIDENCE_MUTATED"


def test_settlement_requires_all_three_tracks():
    ledger, _ = filled_ledger()
    only_ev = (make_track_result("mat_1", "pos_1", track=TrackName.EV_EXIT),)

    with pytest.raises(PaperTransitionError) as error:
        MACHINE.apply_settlement(ledger, only_ev)
    assert error.value.reason_code == "TRACKS_INCOMPLETE"


def test_stale_gap_are_not_ledger_states():
    ledger, _ = filled_ledger()
    assert ledger.lifecycle is PaperLifecycleState.FILLED
    # Overlays never appear as lifecycle values.
    assert "STALE" not in {state.name for state in PaperLifecycleState}
    assert "GAP" not in {state.name for state in PaperLifecycleState}
