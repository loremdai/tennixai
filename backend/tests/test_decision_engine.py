"""Decision engine table tests (T63).

Every hard gate and every action gets an explicit case: MARKET_ONLY,
NO BET with stable reason codes, WAIT with a dynamically solved maximum
price, BUY, HOLD, SELL and the separate LOCK PROFIT risk option. Stale/gap
overlays revoke new BUY/SELL without replacing ledger truth.
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.decision.engine import DecisionEngine, DecisionInput
from app.decision.models import DecisionAction
from app.decision.policy import PolicyArtifact
from app.markets.models import (
    BookLevel,
    MarketExecutionMetadata,
    OrderBookState,
    OutcomeBook,
)
from app.paper.models import PaperPosition, PositionStatus
from app.prediction.models import (
    ModelAvailability,
    PredictionSnapshot,
    ProbabilityEstimate,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
POLICY_PATH = Path(__file__).parent / "fixtures" / "decision" / "policy-v1.json"


@pytest.fixture()
def policy() -> PolicyArtifact:
    return PolicyArtifact.load(POLICY_PATH)


@pytest.fixture()
def engine(policy) -> DecisionEngine:
    return DecisionEngine(policy=policy)


def prediction(
    p1: float = 0.62,
    availability: ModelAvailability = ModelAvailability.AVAILABLE,
    abstain_reason: str | None = None,
) -> PredictionSnapshot:
    if availability is not ModelAvailability.AVAILABLE:
        return PredictionSnapshot(
            match_id="mat_1",
            outcomes=(),
            availability=availability,
            abstain_reason=abstain_reason or "reason",
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )
    return PredictionSnapshot(
        match_id="mat_1",
        outcomes=(
            ProbabilityEstimate(
                player_id="ply_a",
                probability=p1,
                lower=p1 - 0.06,
                upper=min(p1 + 0.06, 1.0),
            ),
            ProbabilityEstimate(
                player_id="ply_b",
                probability=1 - p1,
                lower=max(0.0, 1 - p1 - 0.06),
                upper=1 - p1 + 0.06,
            ),
        ),
        availability=availability,
        model_version="m",
        calibration_version="c",
        data_version="d",
        input_state_version=1,
        as_of=NOW,
    )


def book(
    *,
    asks_a=(("0.55", "100"),),
    bids_a=(("0.52", "100"),),
    stale: bool = False,
) -> OrderBookState:
    def levels(raw):
        return tuple(BookLevel(price=Decimal(p), size=Decimal(s)) for p, s in raw)

    return OrderBookState(
        market_id="mkt_1",
        books=(
            OutcomeBook(
                outcome_player_id="ply_a", bids=levels(bids_a), asks=levels(asks_a)
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=levels((("0.44", "100"),)),
                asks=levels((("0.46", "100"),)),
            ),
        ),
        sequence=9,
        book_hash="book_v9",
        provider_timestamp=NOW,
        received_at=NOW,
        is_stale=stale,
    )


def meta() -> MarketExecutionMetadata:
    return MarketExecutionMetadata(
        market_id="mkt_1",
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("5"),
        fee_rate=Decimal("0"),
        fee_exponent=Decimal("1"),
        taker_only=True,
        maker_base_fee=Decimal("0"),
        taker_base_fee=Decimal("0"),
        sports_delay_seconds=10,
        game_start_time=NOW,
        fetched_at=NOW,
    )


def position(*, shares: str = "20", cost: str = "10.00") -> PaperPosition:
    return PaperPosition(
        id="pos_1",
        match_id="mat_1",
        market_id="mkt_1",
        outcome_player_id="ply_a",
        entry_cost=Decimal(cost),
        shares=Decimal(shares),
        status=PositionStatus.OPEN,
        opened_at=NOW,
        updated_at=NOW,
    )


def base_input(**overrides) -> DecisionInput:
    params = {
        "match_id": "mat_1",
        "market_id": "mkt_1",
        "mapped": True,
        "observation_version": 1,
        "as_of": NOW,
        "prediction": prediction(),
        "book": book(),
        "metadata": meta(),
        "rules_current_hash": "rules_v1",
    }
    params.update(overrides)
    return DecisionInput(**params)


# ---------------------------------------------------------------------------
# Hard gates
# ---------------------------------------------------------------------------


def test_unmapped_market_is_market_only(engine):
    observation = engine.evaluate(
        base_input(mapped=False, market_id=None, book=None, prediction=None)
    )

    assert observation.action is DecisionAction.MARKET_ONLY
    assert observation.reason_code == "MARKET_UNMAPPED"


def test_unpromoted_model_is_no_bet(engine):
    observation = engine.evaluate(
        base_input(
            prediction=prediction(
                availability=ModelAvailability.UNPROMOTED,
                abstain_reason="MODEL_UNPROMOTED",
            )
        )
    )

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "MODEL_UNPROMOTED"


def test_out_of_domain_stays_market_only(engine):
    observation = engine.evaluate(
        base_input(
            prediction=prediction(
                availability=ModelAvailability.UNAVAILABLE,
                abstain_reason="OUT_OF_DOMAIN",
            )
        )
    )

    assert observation.action is DecisionAction.MARKET_ONLY
    assert observation.reason_code == "OUT_OF_DOMAIN"


def test_incomplete_data_is_no_bet(engine):
    observation = engine.evaluate(
        base_input(
            prediction=prediction(
                availability=ModelAvailability.UNAVAILABLE,
                abstain_reason="DATA_INCOMPLETE",
            )
        )
    )

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "DATA_INCOMPLETE"


def test_rule_change_suppresses_actions(engine):
    observation = engine.evaluate(
        base_input(rules_current_hash="rules_v2", rules_frozen_hash="rules_v1")
    )

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "RULE_CHANGED"


def test_stale_overlay_revokes_new_buy(engine):
    observation = engine.evaluate(base_input(is_stale=True))

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "STALE"
    assert observation.is_stale


def test_stale_overlay_keeps_hold_for_existing_position(engine):
    observation = engine.evaluate(
        base_input(
            is_stale=True, position=position(), book=book(bids_a=(("0.52", "100"),))
        )
    )

    assert observation.action is DecisionAction.HOLD
    assert observation.is_stale


def test_gap_overlay_revokes_new_sell(engine):
    observation = engine.evaluate(
        base_input(
            has_gap=True,
            position=position(),
            book=book(bids_a=(("0.90", "100"),)),
        )
    )

    assert observation.action is DecisionAction.HOLD
    assert observation.has_gap
    assert observation.reason_code == "GAP"


def test_model_disagreement_is_no_bet(engine):
    observation = engine.evaluate(base_input(prediction=prediction(p1=0.51)))

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "MODEL_DISAGREEMENT"


def test_insufficient_liquidity_is_no_bet(engine):
    observation = engine.evaluate(
        base_input(book=book(asks_a=(("0.55", "4"),)))  # only $2.20 of depth
    )

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "INSUFFICIENT_LIQUIDITY"


def test_missing_book_is_data_incomplete(engine):
    observation = engine.evaluate(base_input(book=None))

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "DATA_INCOMPLETE"


def test_no_net_edge_when_price_already_fair(engine):
    # Model 0.56 versus an executable 0.55: the gap never reaches the 0.03
    # threshold and no cheaper price exists.
    observation = engine.evaluate(
        base_input(prediction=prediction(p1=0.56), book=book(asks_a=(("0.55", "100"),)))
    )

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "NO_NET_EDGE"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def test_buy_requires_quote_target_and_edge(engine):
    observation = engine.evaluate(base_input())

    assert observation.action is DecisionAction.BUY
    assert observation.target_player_id == "ply_a"
    assert observation.quote is not None
    assert observation.quote.side.value == "entry"
    assert observation.conservative_net_edge == Decimal("0.07")
    assert observation.reason_code is None
    failed_gates = [gate for gate in observation.gates if not gate.passed]
    assert failed_gates == []


def test_wait_shows_dynamically_solved_maximum_price(engine):
    # Model 0.62, threshold 0.03, zero fee: the max acceptable average is
    # exactly 0.59; a 0.595 book does not clear it yet.
    observation = engine.evaluate(base_input(book=book(asks_a=(("0.595", "100"),))))

    assert observation.action is DecisionAction.WAIT
    assert observation.target_player_id == "ply_a"
    assert observation.max_acceptable_price == Decimal("0.5900")
    assert observation.reason_code is None


def test_wait_maximum_price_accounts_for_the_fee_curve(engine, policy):
    engine_with_fee = DecisionEngine(policy=policy)
    metadata = MarketExecutionMetadata(
        market_id="mkt_1",
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("5"),
        fee_rate=Decimal("0.02"),
        fee_exponent=Decimal("1"),
        taker_only=True,
        maker_base_fee=Decimal("0"),
        taker_base_fee=Decimal("0"),
        sports_delay_seconds=10,
        game_start_time=NOW,
        fetched_at=NOW,
    )
    observation = engine_with_fee.evaluate(
        base_input(metadata=metadata, book=book(asks_a=(("0.585", "100"),)))
    )

    # Solving 0.62 - P - 0.02*min(P,1-P) >= 0.03 on the P>0.5 branch gives
    # 0.57 - 0.98*P >= 0, i.e. P <= 0.581632... rounded down to 0.5816.
    assert observation.action is DecisionAction.WAIT
    assert observation.max_acceptable_price is not None
    assert observation.max_acceptable_price == Decimal("0.5816")


def test_hold_while_exit_value_below_ev_threshold(engine):
    observation = engine.evaluate(
        base_input(position=position(), book=book(bids_a=(("0.60", "100"),)))
    )

    assert observation.action is DecisionAction.HOLD
    assert observation.reason_code is None


def test_sell_when_exit_clears_ev_threshold(engine):
    observation = engine.evaluate(
        base_input(position=position(), book=book(bids_a=(("0.75", "100"),)))
    )

    assert observation.action is DecisionAction.SELL
    assert observation.target_player_id == "ply_a"
    assert observation.quote is not None
    assert observation.quote.side.value == "exit"


def test_lock_profit_is_a_separate_option_not_the_primary_action(engine):
    # Exit 0.63 versus entry 0.50/share: 25% profit reached (lock option),
    # but 0.63 < model 0.62 + 0.02 threshold means the EV action is HOLD.
    observation = engine.evaluate(
        base_input(position=position(), book=book(bids_a=(("0.63", "100"),)))
    )

    assert observation.action is DecisionAction.HOLD
    assert observation.lock_profit_available is True


def test_missing_policy_disables_buy_and_sell():
    engine = DecisionEngine(policy=None)

    observation = engine.evaluate(base_input())

    assert observation.action is DecisionAction.NO_BET
    assert observation.reason_code == "POLICY_DISABLED"


def test_observation_carries_versioned_inputs(engine):
    observation = engine.evaluate(base_input(observation_version=7))

    assert observation.observation_version == 7
    assert observation.model_version == "m"
    assert observation.calibration_version == "c"
    assert observation.policy_version == "policy-v1"
    assert observation.as_of == NOW
