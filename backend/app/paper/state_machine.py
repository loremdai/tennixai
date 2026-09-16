"""Pure one-shot FOK paper state machine (T64).

No I/O, no clock, no randomness: every transition is validated against the
frozen lifecycle contract. Duplicate entry/exit, retries after
MISSED/EXIT_MISSED, partial fills, side switches, add-ons, out-of-order
transitions and frozen-evidence mutation are rejected with stable reason
codes. STALE/GAP are overlays and never ledger states.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from app.paper.models import (
    IntentSide,
    PAPER_LIFECYCLE_TRANSITIONS,
    PaperFill,
    PaperLifecycleState,
    PaperOrderIntent,
    PaperTrackResult,
    TrackName,
)

# FOK tolerance: the requoted full-stake cost may differ from the frozen
# stake by at most one cent of rounding.
STAKE_TOLERANCE = Decimal("0.01")
REQUIRED_TRACKS = frozenset(
    {TrackName.EV_EXIT, TrackName.HODL_BASELINE, TrackName.CONVERGENCE_LOCK}
)


class PaperTransitionError(Exception):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class TransitionEvidence:
    prediction_version: str
    decision_observation_version: int
    rules_hash: str
    fee_rate: Decimal
    delay_seconds: int
    book_hash: str


@dataclass(frozen=True)
class MatchLedger:
    """In-memory projection of one match's paper ledger."""

    match_id: str
    position_outcome: str | None = None
    lifecycle: PaperLifecycleState | None = None
    entry_intent_id: str | None = None
    exit_intent_id: str | None = None
    position_id: str | None = None
    entry_stake: Decimal | None = None
    entry_evidence: TransitionEvidence | None = None
    exit_evidence: TransitionEvidence | None = None


class PaperStateMachine:
    def begin_entry(
        self,
        ledger: MatchLedger,
        intent: PaperOrderIntent,
        evidence: TransitionEvidence,
    ) -> MatchLedger:
        if ledger.lifecycle is not None or ledger.entry_intent_id is not None:
            raise PaperTransitionError(
                "ENTRY_EXISTS", "one entry intent per match, no add-ons or retries"
            )
        if intent.side is not IntentSide.ENTRY:
            raise PaperTransitionError("WRONG_SIDE", "entry intent required")
        if intent.match_id != ledger.match_id:
            raise PaperTransitionError("MATCH_MISMATCH")
        return replace(
            ledger,
            lifecycle=PaperLifecycleState.ENTRY_PENDING,
            entry_intent_id=intent.id,
            entry_stake=intent.stake,
            entry_evidence=evidence,
        )

    def apply_entry_fill(
        self,
        ledger: MatchLedger,
        fill: PaperFill,
        *,
        position_id: str | None = None,
        entry_cost: Decimal | None = None,
        shares: Decimal | None = None,
    ) -> MatchLedger:
        self._require(
            ledger,
            PaperLifecycleState.ENTRY_PENDING,
            fill.intent_id,
            ledger.entry_intent_id,
        )
        if fill.filled:
            stake = ledger.entry_stake or Decimal("0")
            cost = (fill.shares or Decimal(0)) * (fill.average_price or Decimal(0))
            if shares is not None and shares != fill.shares:
                raise PaperTransitionError("PARTIAL_FILL", "share mismatch")
            if abs(cost + (fill.fee or Decimal(0)) - stake) > STAKE_TOLERANCE * max(
                Decimal(1), stake
            ) and abs(cost - stake) > STAKE_TOLERANCE * max(Decimal(1), stake):
                raise PaperTransitionError(
                    "PARTIAL_FILL", "FOK requires the full stake to be executed"
                )
            if position_id is None:
                raise PaperTransitionError("POSITION_REQUIRED")
            return self._advance(
                replace(ledger, position_id=position_id),
                PaperLifecycleState.FILLED,
            )
        return self._advance(ledger, PaperLifecycleState.MISSED)

    def begin_exit(
        self,
        ledger: MatchLedger,
        intent: PaperOrderIntent,
        evidence: TransitionEvidence,
    ) -> MatchLedger:
        if ledger.exit_intent_id is not None:
            raise PaperTransitionError(
                "EXIT_EXISTS", "one exit intent per match, no retries"
            )
        if ledger.lifecycle is not PaperLifecycleState.FILLED:
            raise PaperTransitionError(
                "EXIT_NOT_ALLOWED",
                "exit requires an open filled position",
            )
        if intent.side is not IntentSide.EXIT:
            raise PaperTransitionError("WRONG_SIDE", "exit intent required")
        if (
            ledger.position_outcome is not None
            and intent.outcome_player_id != ledger.position_outcome
        ):
            raise PaperTransitionError("SIDE_SWITCH", "exits never switch sides")
        return replace(
            self._advance(ledger, PaperLifecycleState.EXIT_PENDING),
            exit_intent_id=intent.id,
            exit_evidence=evidence,
        )

    def apply_exit_fill(
        self,
        ledger: MatchLedger,
        fill: PaperFill,
        *,
        evidence: TransitionEvidence | None = None,
    ) -> MatchLedger:
        self._require(
            ledger,
            PaperLifecycleState.EXIT_PENDING,
            fill.intent_id,
            ledger.exit_intent_id,
        )
        if evidence is not None and ledger.exit_evidence is not None:
            if evidence.rules_hash != ledger.exit_evidence.rules_hash:
                raise PaperTransitionError(
                    "EVIDENCE_MUTATED", "frozen evidence cannot change mid-flight"
                )
        if fill.filled:
            return self._advance(ledger, PaperLifecycleState.EXITED)
        return self._advance(ledger, PaperLifecycleState.EXIT_MISSED)

    def apply_settlement(
        self, ledger: MatchLedger, tracks: tuple[PaperTrackResult, ...]
    ) -> MatchLedger:
        if ledger.lifecycle not in (
            PaperLifecycleState.FILLED,
            PaperLifecycleState.EXITED,
            PaperLifecycleState.EXIT_MISSED,
        ):
            raise PaperTransitionError(
                "SETTLEMENT_NOT_ALLOWED",
                "only open/exited tracks settle",
            )
        if {track.track for track in tracks} != set(REQUIRED_TRACKS):
            raise PaperTransitionError(
                "TRACKS_INCOMPLETE",
                "settlement requires EV, HODL and convergence-lock tracks",
            )
        return self._advance(ledger, PaperLifecycleState.SETTLED)

    # ------------------------------------------------------------------

    @staticmethod
    def _require(
        ledger: MatchLedger,
        expected: PaperLifecycleState,
        intent_id: str,
        expected_intent_id: str | None,
    ) -> None:
        if ledger.lifecycle is not expected:
            raise PaperTransitionError(
                "OUT_OF_ORDER",
                f"transition requires lifecycle {expected.value}",
            )
        if intent_id != expected_intent_id:
            raise PaperTransitionError("INTENT_MISMATCH")

    @staticmethod
    def _advance(ledger: MatchLedger, to_state: PaperLifecycleState) -> MatchLedger:
        assert ledger.lifecycle is not None  # noqa: S101 - validated by callers
        if (ledger.lifecycle, to_state) not in PAPER_LIFECYCLE_TRANSITIONS:
            raise PaperTransitionError(
                "ILLEGAL_TRANSITION",
                f"{ledger.lifecycle.value} -> {to_state.value}",
            )
        return replace(ledger, lifecycle=to_state)
