"""Shared canonical P3 object builders for integration tests (T58)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.markets.models import (
    BookLevel,
    ExecutableQuote,
    Market,
    MarketOutcome,
    MarketResolution,
    MarketRules,
    MarketStatus,
    OrderBookState,
    OutcomeBook,
    QuoteSide,
    ResolutionStatus,
)
from app.paper.models import (
    IntentSide,
    IntentStatus,
    PaperFill,
    PaperOrderIntent,
    PaperPosition,
    PaperTrackResult,
    PositionStatus,
    TrackExitKind,
    TrackName,
)
from app.prediction.models import (
    ModelAvailability,
    PredictionSnapshot,
    ProbabilityEstimate,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def unique_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def make_market(
    market_id: str | None = None,
    *,
    match_id: str | None = None,
    status: MarketStatus = MarketStatus.OPEN,
    player_a: str = "ply_a",
    player_b: str = "ply_b",
) -> Market:
    return Market(
        id=market_id or unique_id("mkt"),
        question="Test moneyline winner",
        outcomes=(
            MarketOutcome(player_id=player_a, name="Player One"),
            MarketOutcome(player_id=player_b, name="Player Two"),
        ),
        status=status,
        rules_version=1,
        match_id=match_id,
        event_start=NOW,
        event_end=NOW + timedelta(hours=3),
        provider="polymarket",
        observed_at=NOW,
    )


def make_rules(market_id: str, *, rules_hash: str = "hash_v1", text: str | None = None):
    return MarketRules(
        market_id=market_id,
        rules_text=text or f"Winner resolves to match winner ({rules_hash}).",
        rules_hash=rules_hash,
        resolution_source="polymarket-uma",
        edge_case_semantics="Retirement follows market rules.",
        fetched_at=NOW,
    )


def make_quote(side: QuoteSide = QuoteSide.ENTRY) -> ExecutableQuote:
    return ExecutableQuote(
        market_id="mkt_x",
        outcome_player_id="ply_a",
        side=side,
        stake=Decimal("10.00"),
        shares=Decimal("19.047619"),
        average_price=Decimal("0.525"),
        fee=Decimal("0.05"),
        slippage=Decimal("0.005"),
        is_fillable=True,
        book_hash="book_v7",
        book_sequence=7,
        quoted_at=NOW,
    )


def make_book(market_id: str = "mkt_x") -> OrderBookState:
    return OrderBookState(
        market_id=market_id,
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=(BookLevel(price=Decimal("0.55"), size=Decimal("200")),),
                asks=(BookLevel(price=Decimal("0.57"), size=Decimal("150")),),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=(BookLevel(price=Decimal("0.43"), size=Decimal("180")),),
                asks=(BookLevel(price=Decimal("0.45"), size=Decimal("160")),),
            ),
        ),
        sequence=7,
        book_hash="book_v7",
        provider_timestamp=NOW,
        received_at=NOW,
    )


def make_prediction(match_id: str) -> PredictionSnapshot:
    return PredictionSnapshot(
        match_id=match_id,
        outcomes=(
            ProbabilityEstimate(
                player_id="ply_a", probability=0.62, lower=0.55, upper=0.69
            ),
            ProbabilityEstimate(
                player_id="ply_b", probability=0.38, lower=0.31, upper=0.45
            ),
        ),
        availability=ModelAvailability.AVAILABLE,
        model_version="prematch-elo-v1",
        calibration_version="platt-v1",
        data_version="apidata-v1",
        input_state_version=12,
        as_of=NOW,
    )


def make_observation(
    match_id: str,
    market_id: str,
    *,
    observation_version: int = 1,
    action: DecisionAction = DecisionAction.BUY,
) -> DecisionObservation:
    return DecisionObservation(
        match_id=match_id,
        market_id=market_id,
        action=action,
        observation_version=observation_version,
        target_player_id="ply_a",
        model_version="prematch-elo-v1",
        calibration_version="platt-v1",
        policy_version="policy-v1",
        quote=make_quote(
            side=QuoteSide.EXIT if action is DecisionAction.SELL else QuoteSide.ENTRY
        ),
        conservative_net_edge=Decimal("0.041"),
        gates=(GateResult(gate="liquidity", passed=True),),
        as_of=NOW,
    )


def make_intent(
    match_id: str,
    market_id: str,
    *,
    intent_id: str | None = None,
    side: IntentSide = IntentSide.ENTRY,
    idempotency_key: str | None = None,
) -> PaperOrderIntent:
    return PaperOrderIntent(
        id=intent_id or unique_id("int"),
        match_id=match_id,
        market_id=market_id,
        side=side,
        status=IntentStatus.PENDING,
        idempotency_key=idempotency_key or f"{side.value}:{match_id}:v1",
        outcome_player_id="ply_a",
        stake=Decimal("10.00"),
        delay_seconds=15,
        model_version="prematch-elo-v1",
        policy_version="policy-v1",
        rules_hash="hash_v1",
        quote=make_quote(),
        created_at=NOW,
        expires_at=NOW + timedelta(seconds=45),
    )


def make_entry_fill(intent_id: str, *, filled: bool = True) -> PaperFill:
    if filled:
        return PaperFill(
            intent_id=intent_id,
            filled=True,
            shares=Decimal("19.047619"),
            average_price=Decimal("0.525"),
            fee=Decimal("0.05"),
            executed_book_hash="book_v9",
            executed_at=NOW + timedelta(seconds=20),
        )
    return PaperFill(
        intent_id=intent_id,
        filled=False,
        reason="DEPTH_INSUFFICIENT",
        executed_book_hash="book_v9",
        executed_at=NOW + timedelta(seconds=20),
    )


def make_position(match_id: str, market_id: str, *, position_id: str | None = None):
    return PaperPosition(
        id=position_id or unique_id("pos"),
        match_id=match_id,
        market_id=market_id,
        outcome_player_id="ply_a",
        entry_cost=Decimal("10.00"),
        shares=Decimal("19.047619"),
        status=PositionStatus.OPEN,
        opened_at=NOW,
        updated_at=NOW,
    )


def make_track_result(
    match_id: str,
    position_id: str,
    *,
    track: TrackName = TrackName.EV_EXIT,
) -> PaperTrackResult:
    exit_kind = (
        TrackExitKind.SOLD
        if track is TrackName.EV_EXIT
        else (
            TrackExitKind.HELD
            if track is TrackName.HODL_BASELINE
            else TrackExitKind.CONVERGENCE_LOCKED
        )
    )
    return PaperTrackResult(
        match_id=match_id,
        position_id=position_id,
        track=track,
        exit_kind=exit_kind,
        shares=Decimal("19.047619"),
        exit_average_price=Decimal("0.60")
        if exit_kind is not TrackExitKind.HELD
        else None,
        payout_per_share=Decimal("1.0"),
        gross_payout=Decimal("19.047619"),
        net_pnl=Decimal("8.997619"),
        settled_at=NOW + timedelta(hours=3),
    )


def make_resolution(
    market_id: str,
    *,
    status: ResolutionStatus = ResolutionStatus.FINAL,
) -> MarketResolution:
    payouts = ()
    confirmed_at = None
    if status is ResolutionStatus.FINAL:
        payouts = (
            {"player_id": "ply_a", "payout_per_share": Decimal("1")},
            {"player_id": "ply_b", "payout_per_share": Decimal("0")},
        )
        confirmed_at = NOW + timedelta(hours=4)
    return MarketResolution(
        market_id=market_id,
        status=status,
        rules_version=1,
        payouts=payouts,
        confirmed_at=confirmed_at,
    )
