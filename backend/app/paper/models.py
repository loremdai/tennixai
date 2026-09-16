"""Canonical P3 paper-trading ledger domain models.

Business actions (BUY/SELL) are instantaneous decision conclusions; the models
here are ledger facts. Each match allows at most one entry intent and one exit
intent, both FOK: no partial fills, no retries, no add-ons, no side switches,
no re-entry. ``STALE/GAP`` is an orthogonal overlay, never a ledger state.
Settlement only obeys the provider-final ``MarketResolution``.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from app.domain import FrozenModel
from app.markets.models import ExecutableQuote


class IntentSide(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


class IntentStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    NO_FILL = "no_fill"


class PaperLifecycleState(StrEnum):
    ENTRY_PENDING = "entry_pending"
    FILLED = "filled"
    MISSED = "missed"
    EXIT_PENDING = "exit_pending"
    EXITED = "exited"
    EXIT_MISSED = "exit_missed"
    SETTLED = "settled"


PAPER_LIFECYCLE_TRANSITIONS: frozenset[
    tuple[PaperLifecycleState, PaperLifecycleState]
] = frozenset(
    {
        (PaperLifecycleState.ENTRY_PENDING, PaperLifecycleState.FILLED),
        (PaperLifecycleState.ENTRY_PENDING, PaperLifecycleState.MISSED),
        (PaperLifecycleState.FILLED, PaperLifecycleState.EXIT_PENDING),
        (PaperLifecycleState.FILLED, PaperLifecycleState.SETTLED),
        (PaperLifecycleState.EXIT_PENDING, PaperLifecycleState.EXITED),
        (PaperLifecycleState.EXIT_PENDING, PaperLifecycleState.EXIT_MISSED),
        (PaperLifecycleState.EXITED, PaperLifecycleState.SETTLED),
        (PaperLifecycleState.EXIT_MISSED, PaperLifecycleState.SETTLED),
    }
)


class PaperLifecycleTransition(FrozenModel):
    match_id: str = Field(min_length=1)
    from_state: PaperLifecycleState
    to_state: PaperLifecycleState

    @model_validator(mode="after")
    def validate_transition(self) -> "PaperLifecycleTransition":
        if (self.from_state, self.to_state) not in PAPER_LIFECYCLE_TRANSITIONS:
            raise ValueError(
                f"illegal paper lifecycle transition "
                f"{self.from_state.value} -> {self.to_state.value}"
            )
        return self


class PaperOrderIntent(FrozenModel):
    """The unique one-shot FOK entry or exit intent for one match."""

    id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    market_id: str = Field(min_length=1)
    side: IntentSide
    status: IntentStatus = IntentStatus.PENDING
    idempotency_key: str = Field(min_length=1)
    outcome_player_id: str = Field(min_length=1)
    stake: Decimal = Field(gt=Decimal("0"))
    delay_seconds: int = Field(ge=0)
    model_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    rules_hash: str = Field(min_length=1)
    quote: ExecutableQuote
    created_at: AwareDatetime
    expires_at: AwareDatetime
    no_fill_reason: str | None = None

    @model_validator(mode="after")
    def validate_intent(self) -> "PaperOrderIntent":
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.status is IntentStatus.NO_FILL and not self.no_fill_reason:
            raise ValueError("no_fill intent requires a typed no_fill_reason")
        if self.status is not IntentStatus.NO_FILL and self.no_fill_reason is not None:
            raise ValueError("no_fill_reason is only valid on no_fill intents")
        return self


class PaperFill(FrozenModel):
    """Full FOK fill or no-fill executed against the post-delay order book."""

    intent_id: str = Field(min_length=1)
    filled: bool
    shares: Decimal | None = None
    average_price: Decimal | None = None
    fee: Decimal | None = None
    reason: str | None = None
    executed_book_hash: str = Field(min_length=1)
    executed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_fill_shape(self) -> "PaperFill":
        if self.filled:
            if self.shares is None or self.average_price is None or self.fee is None:
                raise ValueError("fill requires shares, average_price and fee")
            if self.shares <= 0 or self.fee < 0:
                raise ValueError("fill shares must be positive and fee non-negative")
            if not Decimal("0") < self.average_price <= Decimal("1"):
                raise ValueError("fill average_price must lie in (0, 1]")
            if self.reason is not None:
                raise ValueError("successful fill must not carry a no-fill reason")
        else:
            if not self.reason:
                raise ValueError("no-fill requires a typed reason")
            if self.shares is not None or self.average_price is not None:
                raise ValueError("no-fill must not carry execution values")
        return self


class PositionStatus(StrEnum):
    OPEN = "open"
    EXIT_PENDING = "exit_pending"
    EXITED = "exited"
    EXIT_MISSED = "exit_missed"
    SETTLED = "settled"


class PaperPosition(FrozenModel):
    """The single main paper position for one match."""

    id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    market_id: str = Field(min_length=1)
    outcome_player_id: str = Field(min_length=1)
    entry_cost: Decimal = Field(gt=Decimal("0"))
    shares: Decimal = Field(gt=Decimal("0"))
    status: PositionStatus = PositionStatus.OPEN
    opened_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_timeline(self) -> "PaperPosition":
        if self.updated_at < self.opened_at:
            raise ValueError("updated_at must not precede opened_at")
        return self


class TrackName(StrEnum):
    EV_EXIT = "ev_exit"
    HODL_BASELINE = "hodl_baseline"
    CONVERGENCE_LOCK = "convergence_lock"


class TrackExitKind(StrEnum):
    SOLD = "sold"
    EXIT_MISSED = "exit_missed"
    HELD = "held"
    CONVERGENCE_LOCKED = "convergence_locked"


_TRACK_EXIT_KINDS: dict[TrackName, frozenset[TrackExitKind]] = {
    TrackName.EV_EXIT: frozenset({TrackExitKind.SOLD, TrackExitKind.EXIT_MISSED}),
    TrackName.HODL_BASELINE: frozenset({TrackExitKind.HELD}),
    TrackName.CONVERGENCE_LOCK: frozenset({TrackExitKind.CONVERGENCE_LOCKED}),
}


class PaperTrackResult(FrozenModel):
    """Exit/settlement result of the EV main track or a counterfactual track."""

    match_id: str = Field(min_length=1)
    position_id: str = Field(min_length=1)
    track: TrackName
    exit_kind: TrackExitKind
    shares: Decimal = Field(ge=Decimal("0"))
    exit_average_price: Decimal | None = None
    payout_per_share: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    gross_payout: Decimal = Field(ge=Decimal("0"))
    net_pnl: Decimal
    settled_at: AwareDatetime

    @model_validator(mode="after")
    def validate_track_consistency(self) -> "PaperTrackResult":
        if self.exit_kind not in _TRACK_EXIT_KINDS[self.track]:
            raise ValueError(
                f"exit kind {self.exit_kind.value} is not valid on track "
                f"{self.track.value}"
            )
        if self.exit_kind in (TrackExitKind.SOLD, TrackExitKind.CONVERGENCE_LOCKED):
            if self.exit_average_price is None:
                raise ValueError(
                    f"{self.exit_kind.value} requires an exit_average_price"
                )
        return self
