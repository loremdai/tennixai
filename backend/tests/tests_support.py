"""Shared fakes for T64 paper service tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.decision.models import DecisionAction, DecisionObservation, GateResult
from app.markets.models import (
    BookLevel,
    ExecutableQuote,
    MarketExecutionMetadata,
    OrderBookState,
    OutcomeBook,
    QuoteSide,
)
from app.paper.models import (
    IntentSide,
    IntentStatus,
    PaperFill,
    PaperOrderIntent,
    PaperPosition,
    PaperTrackResult,
    PositionStatus,
)
from app.persistence.paper_repositories import (
    IllegalLedgerTransitionError,
    UniqueViolationError,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, start: datetime = NOW) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


_POSITION_TRANSITIONS = {
    PositionStatus.OPEN: {PositionStatus.EXIT_PENDING, PositionStatus.SETTLED},
    PositionStatus.EXIT_PENDING: {
        PositionStatus.EXITED,
        PositionStatus.EXIT_MISSED,
    },
    PositionStatus.EXITED: {PositionStatus.SETTLED},
    PositionStatus.EXIT_MISSED: {PositionStatus.SETTLED},
    PositionStatus.SETTLED: set(),
}


class InMemoryPaperLedger:
    """Deterministic in-memory stand-in mirroring the PostgreSQL ledger's
    one-shot uniqueness and idempotency semantics."""

    def __init__(self) -> None:
        self.intents: dict[str, PaperOrderIntent] = {}
        self.fills: dict[str, PaperFill] = {}
        self.positions: dict[str, PaperPosition] = {}
        self.tracks: list[PaperTrackResult] = []
        self.resolutions: dict[str, object] = {}
        self.log: list[str] = []

    async def create_intent(self, intent: PaperOrderIntent) -> PaperOrderIntent:
        for stored in self.intents.values():
            if stored.idempotency_key == intent.idempotency_key:
                self.log.append("commit:intent")
                return stored
        for stored in self.intents.values():
            if stored.match_id == intent.match_id and stored.side is intent.side:
                raise UniqueViolationError("one-shot intent per match/side")
        self.intents[intent.id] = intent
        self.log.append("commit:intent")
        return intent

    async def get_intent(self, intent_id: str) -> PaperOrderIntent | None:
        return self.intents.get(intent_id)

    async def load_all_intents(self) -> list[PaperOrderIntent]:
        return list(self.intents.values())

    async def load_pending_intents(self) -> tuple[PaperOrderIntent, ...]:
        return tuple(
            intent
            for intent in self.intents.values()
            if intent.status is IntentStatus.PENDING
        )

    async def record_fill(
        self, fill: PaperFill, *, position: PaperPosition | None = None
    ) -> None:
        if fill.intent_id in self.fills:
            return
        intent = self.intents[fill.intent_id]
        self.fills[fill.intent_id] = fill
        self.intents[intent.id] = intent.model_copy(
            update={
                "status": IntentStatus.FILLED if fill.filled else IntentStatus.NO_FILL,
                "no_fill_reason": None if fill.filled else fill.reason,
            }
        )
        if fill.filled and position is not None and intent.side is IntentSide.ENTRY:
            self.positions.setdefault(position.match_id, position)
        self.log.append("commit:fill")

    async def get_fill_for_intent(self, intent_id: str) -> PaperFill | None:
        return self.fills.get(intent_id)

    async def get_position(self, match_id: str) -> PaperPosition | None:
        return self.positions.get(match_id)

    async def update_position_status(
        self, match_id: str, status: PositionStatus, **kwargs
    ) -> None:
        position = self.positions[match_id]
        if position.status is status:
            return
        if status not in _POSITION_TRANSITIONS[position.status]:
            raise IllegalLedgerTransitionError(
                f"{position.status.value} -> {status.value}"
            )
        self.positions[match_id] = position.model_copy(update={"status": status})
        self.log.append("commit:position")

    async def load_unsettled_positions(self) -> tuple[PaperPosition, ...]:
        return tuple(
            position
            for position in self.positions.values()
            if position.status is not PositionStatus.SETTLED
        )

    async def record_track_result(self, result: PaperTrackResult) -> PaperTrackResult:
        for stored in self.tracks:
            if (
                stored.position_id == result.position_id
                and stored.track is result.track
            ):
                return stored
        self.tracks.append(result)
        self.log.append("commit:track")
        return result

    async def load_track_results(self, position_id: str) -> list[PaperTrackResult]:
        return [track for track in self.tracks if track.position_id == position_id]

    async def record_resolution(self, resolution) -> None:
        self.resolutions[resolution.market_id] = resolution
        self.log.append("commit:resolution")

    async def get_resolution(self, market_id: str):
        return self.resolutions.get(market_id)


def _levels(raw) -> tuple[BookLevel, ...]:
    return tuple(BookLevel(price=Decimal(p), size=Decimal(s)) for p, s in raw)


def _book(
    *,
    asks_a=(("0.52", "200"),),
    bids_a=(("0.50", "200"),),
    stale: bool = False,
) -> OrderBookState:
    return OrderBookState(
        market_id="mkt_1",
        books=(
            OutcomeBook(
                outcome_player_id="ply_a",
                bids=_levels(bids_a),
                asks=_levels(asks_a),
            ),
            OutcomeBook(
                outcome_player_id="ply_b",
                bids=_levels((("0.47", "200"),)),
                asks=_levels((("0.49", "200"),)),
            ),
        ),
        sequence=3,
        book_hash="book_exec_v3",
        provider_timestamp=NOW,
        received_at=NOW,
        is_stale=stale,
    )


def _metadata() -> MarketExecutionMetadata:
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


def _observation(
    action: DecisionAction,
    *,
    side: QuoteSide = QuoteSide.ENTRY,
    average: str = "0.525",
    version: int = 1,
    reason: str | None = None,
) -> DecisionObservation:
    quote = ExecutableQuote(
        market_id="mkt_1",
        outcome_player_id="ply_a",
        side=side,
        stake=Decimal("10.00"),
        shares=Decimal("19.047619"),
        average_price=Decimal(average),
        fee=Decimal("0"),
        slippage=Decimal("0"),
        is_fillable=True,
        book_hash="book_signal_v1",
        book_sequence=1,
        quoted_at=NOW,
    )
    params = {
        "match_id": "mat_1",
        "market_id": "mkt_1",
        "action": action,
        "observation_version": version,
        "target_player_id": "ply_a",
        "model_version": "m",
        "calibration_version": "c",
        "policy_version": "policy-v1",
        "quote": quote,
        "conservative_net_edge": Decimal("0.05"),
        "gates": (GateResult(gate="liquidity", passed=True),),
        "as_of": NOW,
    }
    if action is DecisionAction.NO_BET:
        params["reason_code"] = reason or "NO_NET_EDGE"
        params["quote"] = None
        params["conservative_net_edge"] = None
    if action is DecisionAction.WAIT:
        params["max_acceptable_price"] = Decimal("0.55")
        params["quote"] = None
        params["conservative_net_edge"] = None
    if action is DecisionAction.HOLD:
        params["quote"] = None
        params["conservative_net_edge"] = None
    if action is DecisionAction.SELL:
        params["quote"] = quote.model_copy(
            update={"side": QuoteSide.EXIT, "average_price": Decimal("0.50")}
        )
    return DecisionObservation(**params)


def build_service_inputs() -> dict:
    return {
        "book": _book(),
        "thin_book": _book(asks_a=(("0.52", "4"),), bids_a=(("0.50", "5"),)),
        "worse_book": _book(asks_a=(("0.55", "200"),)),
        "stale_book": _book(stale=True),
        "metadata": _metadata(),
        "buy_observation": _observation(DecisionAction.BUY),
        "sell_observation": _observation(DecisionAction.SELL, version=2),
        "observation_for": _observation,
    }
