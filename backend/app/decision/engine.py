"""Versioned decision engine (T63).

Combines one calibrated prediction with two independent executable books,
current market metadata and the versioned policy artifact into exactly one
structured action plus auditable gates. Hard gates fail closed; stale/gap
overlays revoke new BUY/SELL without replacing ledger truth; LOCK PROFIT is
a separately flagged risk option, never the primary action. The engine is
deterministic and never calls an LLM or reads anything but the inputs given.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.decision.models import (
    DecisionAction,
    DecisionObservation,
    DecisionReason,
    GateResult,
)
from app.decision.policy import PolicyArtifact
from app.decision.quotes import (
    compute_exit_quote,
    compute_quote,
    max_acceptable_average_price,
)
from app.markets.models import (
    MarketExecutionMetadata,
    OrderBookState,
    QuoteSide,
)
from app.paper.models import PaperPosition
from app.prediction.models import ModelAvailability, PredictionSnapshot

# A WAIT requires at least half of the BUY edge threshold of raw
# undervaluation versus the best executable ask; below that the market
# essentially agrees with the model and the answer is NO NET EDGE.
WAIT_UNDERVALUATION_FRACTION = 0.5
# Diagnostic-only convergence lock line: 25% over entry cost per share.
LOCK_PROFIT_FACTOR = Decimal("1.25")


@dataclass(frozen=True)
class DecisionInput:
    match_id: str
    observation_version: int
    as_of: datetime
    market_id: str | None = None
    mapped: bool = False
    prediction: PredictionSnapshot | None = None
    book: OrderBookState | None = None
    metadata: MarketExecutionMetadata | None = None
    rules_current_hash: str | None = None
    rules_frozen_hash: str | None = None
    position: PaperPosition | None = None
    is_stale: bool = False
    has_gap: bool = False


class DecisionEngine:
    def __init__(
        self,
        *,
        policy: PolicyArtifact | None,
        stake: Decimal = Decimal("10.00"),
    ) -> None:
        self._policy = policy
        self._stake = stake

    # ------------------------------------------------------------------

    def evaluate(self, data: DecisionInput) -> DecisionObservation:
        gates: list[GateResult] = []

        def gate(name: str, passed: bool, reason: str | None = None) -> bool:
            gates.append(GateResult(gate=name, passed=passed, reason_code=reason))
            return passed

        def observation(
            action: DecisionAction,
            *,
            reason: str | None = None,
            target: str | None = None,
            quote=None,
            edge: Decimal | None = None,
            max_price: Decimal | None = None,
            lock: bool = False,
            hold_value: Decimal | None = None,
        ) -> DecisionObservation:
            return DecisionObservation(
                match_id=data.match_id,
                market_id=data.market_id or "",
                action=action,
                observation_version=data.observation_version,
                model_version=(
                    data.prediction.model_version
                    if data.prediction is not None
                    else "none"
                ),
                calibration_version=(
                    data.prediction.calibration_version
                    if data.prediction is not None
                    else "none"
                ),
                policy_version=(
                    self._policy.policy_version if self._policy else "disabled"
                ),
                target_player_id=target,
                quote=quote,
                conservative_net_edge=edge,
                max_acceptable_price=max_price,
                reason_code=reason,
                gates=tuple(gates),
                is_stale=data.is_stale,
                has_gap=data.has_gap,
                lock_profit_available=lock,
                hold_value=hold_value,
                as_of=data.as_of,
            )

        # 1. Exact mapping gate.
        if not gate(
            "mapping", data.mapped and data.market_id is not None, "MARKET_UNMAPPED"
        ):
            return observation(
                DecisionAction.MARKET_ONLY, reason=DecisionReason.MARKET_UNMAPPED.value
            )

        # 2. Rule stability gate.
        rules_changed = (
            data.rules_frozen_hash is not None
            and data.rules_current_hash != data.rules_frozen_hash
        )
        if not gate("rules", not rules_changed, "RULE_CHANGED"):
            return observation(
                DecisionAction.NO_BET, reason=DecisionReason.RULE_CHANGED.value
            )

        # 3. Model availability gates.
        prediction = data.prediction
        if prediction is None:
            gate("data", False, "DATA_INCOMPLETE")
            return observation(
                DecisionAction.NO_BET, reason=DecisionReason.DATA_INCOMPLETE.value
            )
        if prediction.availability is ModelAvailability.UNPROMOTED:
            reason = prediction.abstain_reason or "MODEL_UNPROMOTED"
            gate("promotion", False, reason)
            return observation(DecisionAction.NO_BET, reason=reason)
        if prediction.availability is ModelAvailability.UNAVAILABLE:
            reason = prediction.abstain_reason or "DATA_INCOMPLETE"
            if reason == "OUT_OF_DOMAIN":
                gate("domain", False, reason)
                return observation(
                    DecisionAction.MARKET_ONLY,
                    reason=DecisionReason.OUT_OF_DOMAIN.value,
                )
            gate("data", False, "DATA_INCOMPLETE")
            return observation(
                DecisionAction.NO_BET,
                reason=DecisionReason.DATA_INCOMPLETE.value,
            )
        gate("model", True)

        # 4. Policy gate.
        policy = self._policy
        if policy is None:
            gate("policy", False, "POLICY_DISABLED")
            return observation(
                DecisionAction.NO_BET, reason=DecisionReason.POLICY_DISABLED.value
            )
        gate("policy", True)

        overlay_reason = (
            DecisionReason.STALE.value
            if data.is_stale
            else DecisionReason.GAP.value
            if data.has_gap
            else None
        )

        # 5. Position branch: HOLD / SELL (+ overlay suppression).
        if data.position is not None:
            return self._evaluate_position(data, prediction, policy, overlay_reason)

        # 6. Pre-position branch.
        first, second = prediction.outcomes
        if first.probability >= second.probability:
            target, model_probability = first.player_id, first.probability
        else:
            target, model_probability = second.player_id, second.probability
        spread = abs(first.probability - second.probability)
        if not gate(
            "model_direction",
            spread >= policy.buy_min_model_probability_gap,
            "MODEL_DISAGREEMENT",
        ):
            return observation(
                DecisionAction.NO_BET,
                reason=DecisionReason.MODEL_DISAGREEMENT.value,
                target=None,
            )

        if data.book is None or data.metadata is None:
            gate("book", False, "DATA_INCOMPLETE")
            return observation(
                DecisionAction.NO_BET, reason=DecisionReason.DATA_INCOMPLETE.value
            )
        if not gate(
            "freshness",
            not data.book.is_stale and not data.is_stale and not data.has_gap,
            "STALE",
        ):
            return observation(DecisionAction.NO_BET, reason=overlay_reason or "STALE")
        gate("book", True)

        quote = compute_quote(
            state=data.book,
            outcome_player_id=target,
            side=QuoteSide.ENTRY,
            stake=self._stake,
            metadata=data.metadata,
            quoted_at=data.as_of,
        )
        if quote is None or not quote.is_fillable:
            gate("liquidity", False, "INSUFFICIENT_LIQUIDITY")
            return observation(
                DecisionAction.NO_BET,
                reason=DecisionReason.INSUFFICIENT_LIQUIDITY.value,
                target=target,
            )
        gate("liquidity", True)

        fee_per_share = (quote.fee / quote.shares) if quote.shares else Decimal("0")
        net_edge = Decimal(str(model_probability)) - quote.average_price - fee_per_share
        if net_edge >= Decimal(str(policy.buy_min_conservative_net_edge)):
            gate("net_edge", True)
            return observation(
                DecisionAction.BUY,
                target=target,
                quote=quote,
                edge=net_edge.quantize(Decimal("0.000001")),
            )
        gate("net_edge", False, "NO_NET_EDGE")

        book_side = next(
            item for item in data.book.books if item.outcome_player_id == target
        )
        best_ask = book_side.asks[0].price if book_side.asks else Decimal("1")
        undervaluation = Decimal(str(model_probability)) - best_ask
        wait_floor = Decimal(str(policy.buy_min_conservative_net_edge)) * Decimal(
            str(WAIT_UNDERVALUATION_FRACTION)
        )
        if undervaluation >= wait_floor:
            max_price = max_acceptable_average_price(
                model_probability,
                min_conservative_net_edge=policy.buy_min_conservative_net_edge,
                fee_rate=data.metadata.fee_rate,
                fee_exponent=data.metadata.fee_exponent,
            )
            return observation(DecisionAction.WAIT, target=target, max_price=max_price)
        return observation(
            DecisionAction.NO_BET, reason=DecisionReason.NO_NET_EDGE.value
        )

    # ------------------------------------------------------------------

    def _evaluate_position(
        self,
        data: DecisionInput,
        prediction: PredictionSnapshot,
        policy: PolicyArtifact,
        overlay_reason: str | None,
    ) -> DecisionObservation:
        position = data.position
        assert position is not None  # noqa: S101 - caller guarantees

        def observation(
            action: DecisionAction,
            *,
            reason: str | None = None,
            quote=None,
            edge: Decimal | None = None,
            lock: bool = False,
            hold_value: Decimal | None = None,
        ) -> DecisionObservation:
            return DecisionObservation(
                match_id=data.match_id,
                market_id=data.market_id or "",
                action=action,
                observation_version=data.observation_version,
                model_version=prediction.model_version,
                calibration_version=prediction.calibration_version,
                policy_version=policy.policy_version,
                target_player_id=position.outcome_player_id,
                quote=quote,
                conservative_net_edge=edge,
                reason_code=reason,
                gates=(),
                is_stale=data.is_stale,
                has_gap=data.has_gap,
                lock_profit_available=lock,
                hold_value=hold_value,
                as_of=data.as_of,
            )

        model_probability = next(
            (
                outcome.probability
                for outcome in prediction.outcomes
                if outcome.player_id == position.outcome_player_id
            ),
            None,
        )
        if model_probability is None:
            return observation(
                DecisionAction.HOLD, reason=DecisionReason.DATA_INCOMPLETE.value
            )

        if overlay_reason is not None:
            # Stale/gap keeps the position, suppresses the new SELL.
            return observation(DecisionAction.HOLD, reason=overlay_reason)

        if data.book is None or data.metadata is None:
            return observation(
                DecisionAction.HOLD, reason=DecisionReason.DATA_INCOMPLETE.value
            )

        exit_quote = compute_exit_quote(
            state=data.book,
            outcome_player_id=position.outcome_player_id,
            shares=position.shares,
            metadata=data.metadata,
            quoted_at=data.as_of,
        )
        entry_cost_per_share = (
            position.entry_cost / position.shares if position.shares else Decimal("0")
        )
        if exit_quote is None or not exit_quote.is_fillable:
            return observation(
                DecisionAction.HOLD, hold_value=Decimal(str(model_probability))
            )

        fee_per_share = (
            (exit_quote.fee / exit_quote.shares) if exit_quote.shares else Decimal("0")
        )
        exit_net = exit_quote.average_price - fee_per_share
        hold_value = Decimal(str(model_probability))
        sell_threshold = hold_value + Decimal(str(policy.sell_min_exit_net_edge))
        lock_available = exit_quote.average_price >= (
            entry_cost_per_share * LOCK_PROFIT_FACTOR
        )

        if exit_net >= sell_threshold:
            return observation(
                DecisionAction.SELL,
                quote=exit_quote,
                edge=(exit_net - hold_value).quantize(Decimal("0.000001")),
                lock=lock_available,
                hold_value=hold_value,
            )
        return observation(
            DecisionAction.HOLD,
            lock=lock_available,
            hold_value=hold_value,
        )
