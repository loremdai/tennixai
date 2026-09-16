"""P3 canonical domain invariant tests (T57).

These tests freeze the P3 domain contract before any provider, persistence,
model-training or UI code exists. Public canonical models only ever carry
internal IDs; provider identifiers live exclusively in the private
``MarketExternalId`` mapping model.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.markets.models import (
    BookLevel,
    ExecutableQuote,
    Market,
    MarketEnvelope,
    MarketEventKind,
    MarketExternalId,
    MarketOutcome,
    MarketResolution,
    MarketRules,
    MarketStatus,
    OrderBookState,
    OutcomeBook,
    QuoteSide,
    ResolutionStatus,
)
from app.markets.providers import MarketDataProvider
from app.paper.models import (
    IntentSide,
    IntentStatus,
    PAPER_LIFECYCLE_TRANSITIONS,
    PaperFill,
    PaperLifecycleState,
    PaperLifecycleTransition,
    PaperOrderIntent,
    PaperPosition,
    PaperTrackResult,
    PositionStatus,
    TrackExitKind,
    TrackName,
)
from app.prediction.models import (
    ModelAvailability,
    PredictionEvidence,
    PredictionSnapshot,
    ProbabilityEstimate,
)


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def make_outcome_book(player_id: str = "ply_a") -> OutcomeBook:
    return OutcomeBook(
        outcome_player_id=player_id,
        bids=(BookLevel(price=Decimal("0.55"), size=Decimal("200")),),
        asks=(BookLevel(price=Decimal("0.57"), size=Decimal("150")),),
    )


def make_order_book() -> OrderBookState:
    return OrderBookState(
        market_id="mkt_a",
        books=(make_outcome_book("ply_a"), make_outcome_book("ply_b")),
        sequence=7,
        book_hash="hash_v7",
        provider_timestamp=NOW,
        received_at=NOW,
    )


def make_market() -> Market:
    return Market(
        id="mkt_a",
        question="Sinner vs Alcaraz winner",
        outcomes=(
            MarketOutcome(player_id="ply_a", name="Jannik Sinner"),
            MarketOutcome(player_id="ply_b", name="Carlos Alcaraz"),
        ),
        status=MarketStatus.OPEN,
        rules_version=1,
        match_id="mat_a",
        event_start=NOW,
        event_end=NOW + timedelta(hours=3),
        provider="polymarket",
        observed_at=NOW,
    )


def make_quote(side: QuoteSide = QuoteSide.ENTRY) -> ExecutableQuote:
    return ExecutableQuote(
        market_id="mkt_a",
        outcome_player_id="ply_a",
        side=side,
        stake=Decimal("10.00"),
        shares=Decimal("19.04"),
        average_price=Decimal("0.525"),
        fee=Decimal("0.05"),
        slippage=Decimal("0.005"),
        is_fillable=True,
        book_hash="hash_v7",
        book_sequence=7,
        quoted_at=NOW,
    )


def make_prediction(
    availability: ModelAvailability = ModelAvailability.AVAILABLE,
) -> PredictionSnapshot:
    return PredictionSnapshot(
        match_id="mat_a",
        outcomes=(
            ProbabilityEstimate(
                player_id="ply_a",
                probability=0.62,
                lower=0.55,
                upper=0.69,
            ),
            ProbabilityEstimate(
                player_id="ply_b",
                probability=0.38,
                lower=0.31,
                upper=0.45,
            ),
        ),
        availability=availability,
        model_version="prematch-elo-v1",
        calibration_version="platt-v1",
        data_version="apidata-v1",
        input_state_version=12,
        evidence=(
            PredictionEvidence(code="surface_rating", description="Hard Elo edge"),
        ),
        as_of=NOW,
    )


def make_observation(**overrides) -> DecisionObservation:
    payload: dict = {
        "match_id": "mat_a",
        "market_id": "mkt_a",
        "action": DecisionAction.BUY,
        "observation_version": 3,
        "target_player_id": "ply_a",
        "model_version": "prematch-elo-v1",
        "calibration_version": "platt-v1",
        "policy_version": "policy-v1",
        "quote": make_quote(),
        "conservative_net_edge": Decimal("0.041"),
        "gates": (GateResult(gate="liquidity", passed=True),),
        "as_of": NOW,
    }
    payload.update(overrides)
    return DecisionObservation(**payload)


def make_intent(**overrides) -> PaperOrderIntent:
    payload: dict = {
        "id": "int_a",
        "match_id": "mat_a",
        "market_id": "mkt_a",
        "side": IntentSide.ENTRY,
        "status": IntentStatus.PENDING,
        "idempotency_key": "entry:mat_a:v1",
        "outcome_player_id": "ply_a",
        "stake": Decimal("10.00"),
        "delay_seconds": 15,
        "model_version": "prematch-elo-v1",
        "policy_version": "policy-v1",
        "rules_hash": "rules_hash_v1",
        "quote": make_quote(),
        "created_at": NOW,
        "expires_at": NOW + timedelta(seconds=45),
    }
    payload.update(overrides)
    return PaperOrderIntent(**payload)


# ---------------------------------------------------------------------------
# Market and order book invariants
# ---------------------------------------------------------------------------


def test_market_rejects_naive_datetimes():
    with pytest.raises(ValidationError):
        Market(
            id="mkt_a",
            question="q",
            outcomes=(
                MarketOutcome(player_id="ply_a", name="A"),
                MarketOutcome(player_id="ply_b", name="B"),
            ),
            status=MarketStatus.OPEN,
            rules_version=1,
            provider="polymarket",
            observed_at=datetime(2026, 9, 16, 12, 0),  # naive
        )


def test_market_requires_two_distinct_outcomes():
    with pytest.raises(ValidationError):
        Market(
            id="mkt_a",
            question="q",
            outcomes=(
                MarketOutcome(player_id="ply_a", name="A"),
                MarketOutcome(player_id="ply_a", name="A again"),
            ),
            status=MarketStatus.OPEN,
            rules_version=1,
            provider="polymarket",
            observed_at=NOW,
        )


def test_public_market_rejects_provider_identifier_fields():
    with pytest.raises(ValidationError):
        Market(
            id="mkt_a",
            question="q",
            outcomes=(
                MarketOutcome(player_id="ply_a", name="A"),
                MarketOutcome(player_id="ply_b", name="B"),
            ),
            status=MarketStatus.OPEN,
            rules_version=1,
            provider="polymarket",
            observed_at=NOW,
            condition_id="0xabc123",
        )


def test_private_external_id_mapping_is_the_only_provider_id_carrier():
    mapping = MarketExternalId(
        market_id="mkt_a",
        provider="polymarket",
        provider_event_id="ev_1",
        condition_id="0xabc123",
        token_ids=("tok_a", "tok_b"),
    )
    assert mapping.condition_id == "0xabc123"
    assert len(mapping.token_ids) == 2


@pytest.mark.parametrize(
    ("price", "size"),
    [
        (Decimal("0.5"), Decimal("-1")),
        (Decimal("0.5"), Decimal("0")),
        (Decimal("0"), Decimal("10")),
        (Decimal("1.5"), Decimal("10")),
        (Decimal("-0.1"), Decimal("10")),
    ],
)
def test_book_level_rejects_negative_or_out_of_range_values(price, size):
    with pytest.raises(ValidationError):
        BookLevel(price=price, size=size)


def test_order_book_rejects_unsorted_and_duplicate_levels():
    with pytest.raises(ValidationError):
        OutcomeBook(
            outcome_player_id="ply_a",
            bids=(
                BookLevel(price=Decimal("0.50"), size=Decimal("10")),
                BookLevel(price=Decimal("0.55"), size=Decimal("10")),
            ),
            asks=(),
        )
    with pytest.raises(ValidationError):
        OutcomeBook(
            outcome_player_id="ply_a",
            bids=(
                BookLevel(price=Decimal("0.55"), size=Decimal("10")),
                BookLevel(price=Decimal("0.55"), size=Decimal("12")),
            ),
            asks=(),
        )
    with pytest.raises(ValidationError):
        OutcomeBook(
            outcome_player_id="ply_a",
            bids=(),
            asks=(
                BookLevel(price=Decimal("0.60"), size=Decimal("10")),
                BookLevel(price=Decimal("0.58"), size=Decimal("10")),
            ),
        )


def test_order_book_state_requires_two_distinct_outcome_books():
    with pytest.raises(ValidationError):
        OrderBookState(
            market_id="mkt_a",
            books=(make_outcome_book("ply_a"), make_outcome_book("ply_a")),
            sequence=1,
            book_hash="h",
            provider_timestamp=NOW,
            received_at=NOW,
        )


def test_order_book_state_rejects_naive_timestamps():
    with pytest.raises(ValidationError):
        OrderBookState(
            market_id="mkt_a",
            books=(make_outcome_book("ply_a"), make_outcome_book("ply_b")),
            sequence=1,
            book_hash="h",
            provider_timestamp=datetime(2026, 9, 16, 12, 0),
            received_at=NOW,
        )


def test_market_rules_requires_hash_and_timezone():
    with pytest.raises(ValidationError):
        MarketRules(
            market_id="mkt_a",
            rules_text="Winner resolves to match winner.",
            rules_hash="",
            resolution_source="polymarket-uma",
            fetched_at=NOW,
        )
    with pytest.raises(ValidationError):
        MarketRules(
            market_id="mkt_a",
            rules_text="Winner resolves to match winner.",
            rules_hash="hash_v1",
            resolution_source="polymarket-uma",
            fetched_at=datetime(2026, 9, 16, 12, 0),
        )


def test_executable_quote_rejects_non_positive_stake_or_negative_fee():
    with pytest.raises(ValidationError):
        ExecutableQuote(**{**make_quote().model_dump(), "stake": Decimal("0")})
    with pytest.raises(ValidationError):
        ExecutableQuote(**{**make_quote().model_dump(), "fee": Decimal("-0.01")})
    with pytest.raises(ValidationError):
        ExecutableQuote(
            **{**make_quote().model_dump(), "average_price": Decimal("1.5")}
        )


def test_final_resolution_requires_complete_payouts_summing_to_one():
    # 50-50 resolution pays $0.50 per share on both outcomes.
    resolution = MarketResolution(
        market_id="mkt_a",
        status=ResolutionStatus.FINAL,
        rules_version=1,
        payouts=(
            {"player_id": "ply_a", "payout_per_share": Decimal("0.5")},
            {"player_id": "ply_b", "payout_per_share": Decimal("0.5")},
        ),
        confirmed_at=NOW,
    )
    assert resolution.status is ResolutionStatus.FINAL

    with pytest.raises(ValidationError):
        MarketResolution(
            market_id="mkt_a",
            status=ResolutionStatus.FINAL,
            rules_version=1,
            payouts=({"player_id": "ply_a", "payout_per_share": Decimal("1.0")},),
            confirmed_at=NOW,
        )
    with pytest.raises(ValidationError):
        MarketResolution(
            market_id="mkt_a",
            status=ResolutionStatus.FINAL,
            rules_version=1,
            payouts=(
                {"player_id": "ply_a", "payout_per_share": Decimal("0.6")},
                {"player_id": "ply_b", "payout_per_share": Decimal("0.5")},
            ),
            confirmed_at=NOW,
        )
    with pytest.raises(ValidationError):
        MarketResolution(
            market_id="mkt_a",
            status=ResolutionStatus.FINAL,
            rules_version=1,
            payouts=(
                {"player_id": "ply_a", "payout_per_share": Decimal("1.0")},
                {"player_id": "ply_b", "payout_per_share": Decimal("0.0")},
            ),
            confirmed_at=None,
        )


def test_envelope_payload_must_match_kind():
    with pytest.raises(ValidationError):
        MarketEnvelope(
            market_id="mkt_a",
            kind=MarketEventKind.BOOK,
            received_at=NOW,
        )
    with pytest.raises(ValidationError):
        MarketEnvelope(
            market_id="mkt_a",
            kind=MarketEventKind.RESOLUTION,
            received_at=NOW,
            book=make_order_book(),
        )
    envelope = MarketEnvelope(
        market_id="mkt_a",
        kind=MarketEventKind.BOOK,
        received_at=NOW,
        book=make_order_book(),
    )
    assert envelope.book is not None


# ---------------------------------------------------------------------------
# Prediction invariants
# ---------------------------------------------------------------------------


def test_probability_estimate_requires_bounds_and_ordered_interval():
    with pytest.raises(ValidationError):
        ProbabilityEstimate(player_id="ply_a", probability=1.2, lower=0.0, upper=1.0)
    with pytest.raises(ValidationError):
        ProbabilityEstimate(player_id="ply_a", probability=-0.1, lower=0.0, upper=1.0)
    with pytest.raises(ValidationError):
        ProbabilityEstimate(player_id="ply_a", probability=0.5, lower=0.6, upper=0.7)


def test_prediction_requires_complementary_probabilities():
    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(
                ProbabilityEstimate(
                    player_id="ply_a", probability=0.6, lower=0.5, upper=0.7
                ),
                ProbabilityEstimate(
                    player_id="ply_b", probability=0.5, lower=0.4, upper=0.6
                ),
            ),
            availability=ModelAvailability.AVAILABLE,
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )


def test_prediction_rejects_duplicate_outcome_players():
    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(
                ProbabilityEstimate(
                    player_id="ply_a", probability=0.5, lower=0.4, upper=0.6
                ),
                ProbabilityEstimate(
                    player_id="ply_a", probability=0.5, lower=0.4, upper=0.6
                ),
            ),
            availability=ModelAvailability.AVAILABLE,
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )


def test_available_prediction_requires_exactly_two_outcomes():
    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(),
            availability=ModelAvailability.AVAILABLE,
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )


def test_abstention_requires_reason_and_no_probabilities():
    abstention = PredictionSnapshot(
        match_id="mat_a",
        outcomes=(),
        availability=ModelAvailability.UNAVAILABLE,
        abstain_reason="OUT_OF_DOMAIN",
        model_version="m",
        calibration_version="c",
        data_version="d",
        input_state_version=1,
        as_of=NOW,
    )
    assert abstention.abstain_reason == "OUT_OF_DOMAIN"

    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(),
            availability=ModelAvailability.UNAVAILABLE,
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )
    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(
                ProbabilityEstimate(
                    player_id="ply_a", probability=0.5, lower=0.4, upper=0.6
                ),
                ProbabilityEstimate(
                    player_id="ply_b", probability=0.5, lower=0.4, upper=0.6
                ),
            ),
            availability=ModelAvailability.UNAVAILABLE,
            abstain_reason="OUT_OF_DOMAIN",
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=NOW,
        )


def test_prediction_rejects_naive_as_of():
    with pytest.raises(ValidationError):
        PredictionSnapshot(
            match_id="mat_a",
            outcomes=(),
            availability=ModelAvailability.UNPROMOTED,
            abstain_reason="MODEL_UNPROMOTED",
            model_version="m",
            calibration_version="c",
            data_version="d",
            input_state_version=1,
            as_of=datetime(2026, 9, 16, 12, 0),
        )


# ---------------------------------------------------------------------------
# Decision invariants
# ---------------------------------------------------------------------------


def test_decision_observation_requires_versioned_inputs():
    with pytest.raises(ValidationError):
        DecisionObservation(
            match_id="mat_a", market_id="mkt_a", action=DecisionAction.BUY
        )


def test_decision_action_enum_is_frozen_set():
    assert {action.value for action in DecisionAction} == {
        "market_only",
        "no_bet",
        "wait",
        "buy",
        "hold",
        "sell",
    }


def test_buy_requires_target_quote_and_edge():
    with pytest.raises(ValidationError):
        make_observation(quote=None)
    with pytest.raises(ValidationError):
        make_observation(conservative_net_edge=None)
    with pytest.raises(ValidationError):
        make_observation(target_player_id=None)


def test_wait_requires_direction_and_dynamic_max_price():
    observation = make_observation(
        action=DecisionAction.WAIT,
        max_acceptable_price=Decimal("0.540"),
        quote=None,
        conservative_net_edge=None,
    )
    assert observation.max_acceptable_price == Decimal("0.540")
    with pytest.raises(ValidationError):
        make_observation(
            action=DecisionAction.WAIT,
            quote=None,
            conservative_net_edge=None,
        )


def test_no_bet_and_market_only_require_reason_code():
    with pytest.raises(ValidationError):
        make_observation(
            action=DecisionAction.NO_BET,
            quote=None,
            conservative_net_edge=None,
            target_player_id=None,
        )
    observation = make_observation(
        action=DecisionAction.NO_BET,
        reason_code="NO_NET_EDGE",
        quote=None,
        conservative_net_edge=None,
        target_player_id=None,
    )
    assert observation.reason_code == "NO_NET_EDGE"


@pytest.mark.parametrize("action", [DecisionAction.BUY, DecisionAction.SELL])
def test_stale_or_gap_overlay_revokes_new_buy_and_sell(action):
    with pytest.raises(ValidationError):
        make_observation(action=action, is_stale=True)
    with pytest.raises(ValidationError):
        make_observation(action=action, has_gap=True)
    # HOLD remains legal under the overlay: it is not a new action.
    hold = make_observation(
        action=DecisionAction.HOLD,
        is_stale=True,
        target_player_id=None,
        quote=None,
        conservative_net_edge=None,
    )
    assert hold.is_stale


def test_gate_result_failure_requires_reason_code():
    with pytest.raises(ValidationError):
        GateResult(gate="freshness", passed=False)
    gate = GateResult(gate="freshness", passed=False, reason_code="STALE")
    assert gate.reason_code == "STALE"


# ---------------------------------------------------------------------------
# Paper lifecycle invariants
# ---------------------------------------------------------------------------


def test_lifecycle_transition_table_matches_spec():
    assert PAPER_LIFECYCLE_TRANSITIONS == frozenset(
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


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (PaperLifecycleState.ENTRY_PENDING, PaperLifecycleState.FILLED),
        (PaperLifecycleState.ENTRY_PENDING, PaperLifecycleState.MISSED),
        (PaperLifecycleState.FILLED, PaperLifecycleState.EXIT_PENDING),
        (PaperLifecycleState.EXIT_PENDING, PaperLifecycleState.EXIT_MISSED),
        (PaperLifecycleState.EXIT_MISSED, PaperLifecycleState.SETTLED),
    ],
)
def test_legal_lifecycle_transitions(from_state, to_state):
    transition = PaperLifecycleTransition(
        match_id="mat_a", from_state=from_state, to_state=to_state
    )
    assert transition.to_state is to_state


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (PaperLifecycleState.MISSED, PaperLifecycleState.ENTRY_PENDING),  # no retry
        (PaperLifecycleState.MISSED, PaperLifecycleState.FILLED),
        (PaperLifecycleState.ENTRY_PENDING, PaperLifecycleState.EXITED),  # out of order
        (
            PaperLifecycleState.EXIT_MISSED,
            PaperLifecycleState.EXIT_PENDING,
        ),  # no re-exit
        (PaperLifecycleState.SETTLED, PaperLifecycleState.FILLED),  # terminal
        (PaperLifecycleState.FILLED, PaperLifecycleState.FILLED),  # self transition
        (PaperLifecycleState.EXITED, PaperLifecycleState.ENTRY_PENDING),  # no re-entry
    ],
)
def test_illegal_lifecycle_transitions_are_rejected(from_state, to_state):
    with pytest.raises(ValidationError):
        PaperLifecycleTransition(
            match_id="mat_a", from_state=from_state, to_state=to_state
        )


def test_stale_and_gap_are_overlays_not_ledger_states():
    values = {state.value for state in PaperLifecycleState}
    assert "stale" not in values
    assert "gap" not in values


def test_intent_requires_expiry_after_creation():
    with pytest.raises(ValidationError):
        make_intent(expires_at=NOW - timedelta(seconds=1))


def test_intent_no_fill_reason_must_match_status():
    with pytest.raises(ValidationError):
        make_intent(status=IntentStatus.NO_FILL)
    with pytest.raises(ValidationError):
        make_intent(status=IntentStatus.FILLED, no_fill_reason="BOOK_UNVERIFIABLE")
    intent = make_intent(
        status=IntentStatus.NO_FILL, no_fill_reason="BOOK_UNVERIFIABLE"
    )
    assert intent.no_fill_reason == "BOOK_UNVERIFIABLE"


def test_intent_rejects_negative_delay_or_stake():
    with pytest.raises(ValidationError):
        make_intent(delay_seconds=-1)
    with pytest.raises(ValidationError):
        make_intent(stake=Decimal("0"))


def test_fill_shape_depends_on_filled_flag():
    fill = PaperFill(
        intent_id="int_a",
        filled=True,
        shares=Decimal("19.04"),
        average_price=Decimal("0.525"),
        fee=Decimal("0.05"),
        executed_book_hash="hash_v9",
        executed_at=NOW,
    )
    assert fill.filled
    with pytest.raises(ValidationError):
        PaperFill(
            intent_id="int_a",
            filled=True,
            executed_book_hash="hash_v9",
            executed_at=NOW,
        )
    no_fill = PaperFill(
        intent_id="int_a",
        filled=False,
        reason="DEPTH_INSUFFICIENT",
        executed_book_hash="hash_v9",
        executed_at=NOW,
    )
    assert no_fill.reason == "DEPTH_INSUFFICIENT"
    with pytest.raises(ValidationError):
        PaperFill(
            intent_id="int_a",
            filled=False,
            executed_book_hash="hash_v9",
            executed_at=NOW,
        )
    with pytest.raises(ValidationError):
        PaperFill(
            intent_id="int_a",
            filled=True,
            shares=Decimal("19.04"),
            average_price=Decimal("0.525"),
            fee=Decimal("0.05"),
            reason="unexpected",
            executed_book_hash="hash_v9",
            executed_at=NOW,
        )


def test_position_rejects_non_positive_cost_or_shares():
    position = PaperPosition(
        id="pos_a",
        match_id="mat_a",
        market_id="mkt_a",
        outcome_player_id="ply_a",
        entry_cost=Decimal("10.00"),
        shares=Decimal("19.04"),
        status=PositionStatus.OPEN,
        opened_at=NOW,
        updated_at=NOW,
    )
    assert position.status is PositionStatus.OPEN
    with pytest.raises(ValidationError):
        PaperPosition(
            id="pos_a",
            match_id="mat_a",
            market_id="mkt_a",
            outcome_player_id="ply_a",
            entry_cost=Decimal("0"),
            shares=Decimal("19.04"),
            opened_at=NOW,
            updated_at=NOW,
        )
    with pytest.raises(ValidationError):
        PaperPosition(
            id="pos_a",
            match_id="mat_a",
            market_id="mkt_a",
            outcome_player_id="ply_a",
            entry_cost=Decimal("10.00"),
            shares=Decimal("-1"),
            opened_at=NOW,
            updated_at=NOW,
        )


def test_track_result_exit_kind_must_match_track():
    result = PaperTrackResult(
        match_id="mat_a",
        position_id="pos_a",
        track=TrackName.EV_EXIT,
        exit_kind=TrackExitKind.SOLD,
        shares=Decimal("19.04"),
        exit_average_price=Decimal("0.60"),
        payout_per_share=Decimal("1.0"),
        gross_payout=Decimal("19.04"),
        net_pnl=Decimal("8.99"),
        settled_at=NOW,
    )
    assert result.track is TrackName.EV_EXIT
    with pytest.raises(ValidationError):
        PaperTrackResult(
            match_id="mat_a",
            position_id="pos_a",
            track=TrackName.HODL_BASELINE,
            exit_kind=TrackExitKind.SOLD,
            shares=Decimal("19.04"),
            exit_average_price=Decimal("0.60"),
            payout_per_share=Decimal("1.0"),
            gross_payout=Decimal("19.04"),
            net_pnl=Decimal("8.99"),
            settled_at=NOW,
        )
    with pytest.raises(ValidationError):
        PaperTrackResult(
            match_id="mat_a",
            position_id="pos_a",
            track=TrackName.CONVERGENCE_LOCK,
            exit_kind=TrackExitKind.CONVERGENCE_LOCKED,
            shares=Decimal("19.04"),
            payout_per_share=Decimal("1.0"),
            gross_payout=Decimal("19.04"),
            net_pnl=Decimal("8.99"),
            settled_at=NOW,
        )


def test_three_track_names_are_fixed():
    assert {track.value for track in TrackName} == {
        "ev_exit",
        "hodl_baseline",
        "convergence_lock",
    }
    assert {kind.value for kind in TrackExitKind} == {
        "sold",
        "exit_missed",
        "held",
        "convergence_locked",
    }


# ---------------------------------------------------------------------------
# Provider protocol boundary
# ---------------------------------------------------------------------------


def test_market_data_provider_protocol_is_satisfied_by_read_only_fake():
    class FakeMarketDataProvider:
        async def list_tennis_moneylines(self) -> tuple[Market, ...]:
            return (make_market(),)

        async def get_market(self, market_id: str) -> Market:
            return make_market()

        async def get_order_book(self, market_id: str) -> OrderBookState:
            return make_order_book()

        def subscribe_order_books(self, market_ids: tuple[str, ...]):
            async def generator():
                yield MarketEnvelope(
                    market_id="mkt_a",
                    kind=MarketEventKind.BOOK,
                    received_at=NOW,
                    book=make_order_book(),
                )

            return generator()

        async def get_resolution(self, market_id: str) -> MarketResolution | None:
            return None

    provider = FakeMarketDataProvider()
    assert isinstance(provider, MarketDataProvider)
