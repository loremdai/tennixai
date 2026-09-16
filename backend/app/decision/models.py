"""Canonical P3 decision domain models.

A ``DecisionObservation`` is an instantaneous engine conclusion, not a
position. Ledger facts live in ``app.paper.models``. Every observation carries
the versioned prediction/policy inputs it was computed from so that any real
BUY/SELL label can be traced back to prediction, quote, policy, book and
ledger transition.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from app.domain import FrozenModel
from app.markets.models import ExecutableQuote, QuoteSide


class DecisionAction(StrEnum):
    MARKET_ONLY = "market_only"
    NO_BET = "no_bet"
    WAIT = "wait"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class DecisionReason(StrEnum):
    """Stable user-visible reason codes for non-actionable observations."""

    MARKET_UNMAPPED = "MARKET_UNMAPPED"
    MODEL_UNPROMOTED = "MODEL_UNPROMOTED"
    PROMOTION_NOT_GRANTED = "PROMOTION_NOT_GRANTED"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    POLICY_DISABLED = "POLICY_DISABLED"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"
    RULE_CHANGED = "RULE_CHANGED"
    STALE = "STALE"
    GAP = "GAP"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    NO_NET_EDGE = "NO_NET_EDGE"


class GateResult(FrozenModel):
    gate: str = Field(min_length=1)
    passed: bool
    reason_code: str | None = None

    @model_validator(mode="after")
    def validate_failure_reason(self) -> "GateResult":
        if not self.passed and not self.reason_code:
            raise ValueError("failed gate requires a stable reason_code")
        return self


class DecisionObservation(FrozenModel):
    match_id: str = Field(min_length=1)
    # Empty for MARKET_ONLY observations of not-yet-mapped markets; an
    # internal market id otherwise. Never a provider identifier.
    market_id: str = ""
    action: DecisionAction
    observation_version: int = Field(ge=1)
    model_version: str = Field(min_length=1)
    calibration_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    target_player_id: str | None = None
    quote: ExecutableQuote | None = None
    conservative_net_edge: Decimal | None = None
    max_acceptable_price: Decimal | None = None
    reason_code: str | None = None
    gates: tuple[GateResult, ...] = ()
    is_stale: bool = False
    has_gap: bool = False
    lock_profit_available: bool = False
    hold_value: Decimal | None = None
    as_of: AwareDatetime

    @model_validator(mode="after")
    def validate_action_inputs(self) -> "DecisionObservation":
        if self.is_stale or self.has_gap:
            if self.action in (DecisionAction.BUY, DecisionAction.SELL):
                raise ValueError("stale/gap overlay revokes new BUY/SELL actions")
        if self.action is DecisionAction.BUY:
            if (
                self.target_player_id is None
                or self.quote is None
                or self.conservative_net_edge is None
            ):
                raise ValueError(
                    "BUY requires target player, executable quote and conservative net edge"
                )
        if self.action is DecisionAction.SELL:
            if self.target_player_id is None or self.quote is None:
                raise ValueError("SELL requires target player and exit quote")
        if self.action is DecisionAction.WAIT:
            if self.target_player_id is None or self.max_acceptable_price is None:
                raise ValueError(
                    "WAIT requires an undervalued direction and a dynamic maximum price"
                )
        if self.action in (DecisionAction.NO_BET, DecisionAction.MARKET_ONLY):
            if not self.reason_code:
                raise ValueError(f"{self.action.value} requires a stable reason_code")
        if self.quote is not None:
            expected_side = (
                QuoteSide.EXIT
                if self.action is DecisionAction.SELL
                else QuoteSide.ENTRY
            )
            if self.quote.side is not expected_side:
                raise ValueError(
                    f"quote side {self.quote.side.value} does not match action "
                    f"{self.action.value} (expected {expected_side.value})"
                )
        return self
