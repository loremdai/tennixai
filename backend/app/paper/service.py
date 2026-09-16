"""Transactional paper trading service (T64).

The first eligible BUY and the first EV SELL become the only entry/exit
attempts for a match. Execution requotes only after the market's actual
sports delay and requires the full $10 stake or the full position within
the frozen limit (FOK). An unverifiable book produces a typed
`BOOK_UNVERIFIABLE` no-fill, never a synthetic fill. PostgreSQL commits
precede every externally visible publish; settlement obeys provider-final
resolution only.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from decimal import Decimal

from app.decision.models import DecisionAction, DecisionObservation
from app.decision.quotes import compute_exit_quote, compute_quote
from app.markets.models import (
    MarketExecutionMetadata,
    MarketResolution,
    OrderBookState,
    QuoteSide,
)
from app.paper.models import (
    IntentSide,
    PaperFill,
    PaperOrderIntent,
    PaperPosition,
    PositionStatus,
)
from app.paper.settlement import SettlementBlocked, interpret_settlement
from app.persistence.paper_repositories import UniqueViolationError

INTENT_GRACE_SECONDS = 300


class PaperTradingService:
    def __init__(
        self,
        *,
        ledger,
        clock: Callable[[], datetime],
        publish: Callable[[str], Awaitable[None]],
    ) -> None:
        self._ledger = ledger
        self._clock = clock
        self._publish = publish

    # ------------------------------------------------------------------
    # Decision intake
    # ------------------------------------------------------------------

    async def on_decision(
        self,
        observation: DecisionObservation,
        *,
        book: OrderBookState | None,
        metadata: MarketExecutionMetadata | None,
        rules_hash: str | None,
    ) -> None:
        if observation.action is DecisionAction.BUY:
            await self._begin_entry(
                observation, metadata=metadata, rules_hash=rules_hash
            )
        elif observation.action is DecisionAction.SELL:
            await self._begin_exit(
                observation, metadata=metadata, rules_hash=rules_hash
            )
        # HOLD/WAIT/NO_BET/MARKET_ONLY create nothing.

    async def _begin_entry(
        self,
        observation: DecisionObservation,
        *,
        metadata: MarketExecutionMetadata | None,
        rules_hash: str | None,
    ) -> None:
        if observation.quote is None or observation.target_player_id is None:
            return
        if await self._ledger.get_position(observation.match_id) is not None:
            return
        if metadata is None:
            return
        now = self._clock()
        delay = metadata.sports_delay_seconds
        intent = PaperOrderIntent(
            id=f"int_entry_{observation.match_id}",
            match_id=observation.match_id,
            market_id=observation.market_id,
            side=IntentSide.ENTRY,
            idempotency_key=f"entry:{observation.match_id}:v1",
            outcome_player_id=observation.target_player_id,
            stake=observation.quote.stake,
            delay_seconds=delay,
            model_version=observation.model_version,
            policy_version=observation.policy_version,
            rules_hash=rules_hash or "unfrozen",
            quote=observation.quote,
            created_at=now,
            expires_at=now + timedelta(seconds=delay + INTENT_GRACE_SECONDS),
        )
        try:
            await self._ledger.create_intent(intent)
        except UniqueViolationError:
            return  # one-shot: an entry intent already exists
        await self._publish(f"entry_pending:{observation.match_id}")

    async def _begin_exit(
        self,
        observation: DecisionObservation,
        *,
        metadata: MarketExecutionMetadata | None,
        rules_hash: str | None,
    ) -> None:
        if observation.quote is None:
            return
        position = await self._ledger.get_position(observation.match_id)
        if position is None or position.status is not PositionStatus.OPEN:
            return
        if metadata is None:
            return
        existing = [
            intent
            for intent in await self._ledger.load_all_intents()
            if intent.match_id == observation.match_id
            and intent.side is IntentSide.EXIT
        ]
        if existing:
            return  # one-shot exit
        now = self._clock()
        delay = metadata.sports_delay_seconds
        intent = PaperOrderIntent(
            id=f"int_exit_{observation.match_id}",
            match_id=observation.match_id,
            market_id=observation.market_id,
            side=IntentSide.EXIT,
            idempotency_key=f"exit:{observation.match_id}:v1",
            outcome_player_id=position.outcome_player_id,
            stake=(position.shares * observation.quote.average_price).quantize(
                Decimal("0.000001")
            ),
            delay_seconds=delay,
            model_version=observation.model_version,
            policy_version=observation.policy_version,
            rules_hash=rules_hash or "unfrozen",
            quote=observation.quote,
            created_at=now,
            expires_at=now + timedelta(seconds=delay + INTENT_GRACE_SECONDS),
        )
        try:
            await self._ledger.create_intent(intent)
        except UniqueViolationError:
            return
        await self._ledger.update_position_status(
            observation.match_id, PositionStatus.EXIT_PENDING
        )
        await self._publish(f"exit_pending:{observation.match_id}")

    # ------------------------------------------------------------------
    # Delayed FOK execution
    # ------------------------------------------------------------------

    async def execute_due_intents(
        self,
        *,
        book: OrderBookState | None,
        metadata: MarketExecutionMetadata | None,
        market_id: str | None = None,
    ) -> None:
        now = self._clock()
        for intent in await self._ledger.load_pending_intents():
            if market_id is not None and intent.market_id != market_id:
                continue
            due_at = intent.created_at + timedelta(seconds=intent.delay_seconds)
            if now < due_at:
                continue  # never requote before the actual sports delay
            if now > intent.expires_at:
                await self._no_fill(intent, "EXPIRED", now)
                continue
            if book is None or book.is_stale or metadata is None:
                await self._no_fill(intent, "BOOK_UNVERIFIABLE", now)
                continue
            if intent.side is IntentSide.ENTRY:
                await self._execute_entry(intent, book, metadata, now)
            else:
                await self._execute_exit(intent, book, metadata, now)

    async def _execute_entry(
        self,
        intent: PaperOrderIntent,
        book: OrderBookState,
        metadata: MarketExecutionMetadata,
        now: datetime,
    ) -> None:
        quote = compute_quote(
            state=book,
            outcome_player_id=intent.outcome_player_id,
            side=QuoteSide.ENTRY,
            stake=intent.stake,
            metadata=metadata,
            quoted_at=now,
        )
        if quote is None or not quote.is_fillable:
            await self._no_fill(intent, "DEPTH_INSUFFICIENT", now, book=book)
            return
        if quote.average_price > intent.quote.average_price:
            await self._no_fill(intent, "PRICE_EXCEEDED", now, book=book)
            return
        fill = PaperFill(
            intent_id=intent.id,
            filled=True,
            shares=quote.shares,
            average_price=quote.average_price,
            fee=quote.fee,
            executed_book_hash=book.book_hash,
            executed_at=now,
        )
        position = PaperPosition(
            id=f"pos_{intent.match_id}",
            match_id=intent.match_id,
            market_id=intent.market_id,
            outcome_player_id=intent.outcome_player_id,
            entry_cost=quote.stake,
            shares=quote.shares,
            status=PositionStatus.OPEN,
            opened_at=now,
            updated_at=now,
        )
        await self._ledger.record_fill(fill, position=position)
        await self._publish(f"filled:{intent.match_id}")

    async def _execute_exit(
        self,
        intent: PaperOrderIntent,
        book: OrderBookState,
        metadata: MarketExecutionMetadata,
        now: datetime,
    ) -> None:
        position = await self._ledger.get_position(intent.match_id)
        if position is None:
            await self._no_fill(intent, "POSITION_MISSING", now)
            return
        quote = compute_exit_quote(
            state=book,
            outcome_player_id=intent.outcome_player_id,
            shares=position.shares,
            metadata=metadata,
            quoted_at=now,
        )
        if quote is None or not quote.is_fillable:
            await self._no_fill(intent, "DEPTH_INSUFFICIENT", now, book=book)
            await self._ledger.update_position_status(
                intent.match_id, PositionStatus.EXIT_MISSED
            )
            await self._publish(f"exit_missed:{intent.match_id}")
            return
        if quote.average_price < intent.quote.average_price:
            await self._no_fill(intent, "PRICE_EXCEEDED", now, book=book)
            await self._ledger.update_position_status(
                intent.match_id, PositionStatus.EXIT_MISSED
            )
            await self._publish(f"exit_missed:{intent.match_id}")
            return
        fill = PaperFill(
            intent_id=intent.id,
            filled=True,
            shares=quote.shares,
            average_price=quote.average_price,
            fee=quote.fee,
            executed_book_hash=book.book_hash,
            executed_at=now,
        )
        await self._ledger.record_fill(fill)
        await self._ledger.update_position_status(
            intent.match_id, PositionStatus.EXITED
        )
        await self._publish(f"exited:{intent.match_id}")

    async def _no_fill(
        self,
        intent: PaperOrderIntent,
        reason: str,
        now: datetime,
        *,
        book: OrderBookState | None = None,
    ) -> None:
        fill = PaperFill(
            intent_id=intent.id,
            filled=False,
            reason=reason,
            executed_book_hash=book.book_hash if book is not None else "unverifiable",
            executed_at=now,
        )
        await self._ledger.record_fill(fill)
        await self._publish(f"no_fill:{intent.match_id}:{reason}")

    # ------------------------------------------------------------------
    # Provider-final settlement
    # ------------------------------------------------------------------

    async def settle_market(
        self,
        market_id: str,
        resolution: MarketResolution,
        *,
        convergence_lock_price: Decimal | None = None,
    ) -> None:
        await self._ledger.record_resolution(resolution)
        for position in await self._ledger.load_unsettled_positions():
            if position.market_id != market_id:
                continue
            exit_intent = next(
                (
                    intent
                    for intent in await self._ledger.load_all_intents()
                    if intent.match_id == position.match_id
                    and intent.side is IntentSide.EXIT
                ),
                None,
            )
            exit_proceeds: Decimal | None = None
            exit_fee = Decimal("0")
            exit_kind = "held"
            if position.status is PositionStatus.EXITED and exit_intent is not None:
                exit_fill = await self._ledger.get_fill_for_intent(exit_intent.id)
                if exit_fill is not None and exit_fill.filled:
                    exit_proceeds = (
                        exit_fill.shares * exit_fill.average_price
                    ).quantize(Decimal("0.000001"))
                    exit_fee = exit_fill.fee or Decimal("0")
                    exit_kind = "sold"
            elif position.status is PositionStatus.EXIT_MISSED:
                exit_kind = "exit_missed"

            entry_intent = next(
                (
                    intent
                    for intent in await self._ledger.load_all_intents()
                    if intent.match_id == position.match_id
                    and intent.side is IntentSide.ENTRY
                ),
                None,
            )
            entry_fee = Decimal("0")
            if entry_intent is not None:
                entry_fill = await self._ledger.get_fill_for_intent(entry_intent.id)
                if entry_fill is not None and entry_fill.filled:
                    entry_fee = entry_fill.fee or Decimal("0")

            try:
                tracks = interpret_settlement(
                    position={
                        "match_id": position.match_id,
                        "market_id": position.market_id,
                        "position_id": position.id,
                        "outcome_player_id": position.outcome_player_id,
                        "entry_cost": position.entry_cost,
                        "shares": position.shares,
                        "exit_kind": exit_kind,
                    },
                    resolution=resolution,
                    exit_proceeds=exit_proceeds,
                    entry_fee=entry_fee,
                    exit_fee=exit_fee,
                    convergence_lock_price=convergence_lock_price,
                )
            except SettlementBlocked as blocked:
                await self._publish(
                    f"settlement_blocked:{market_id}:{blocked.reason_code}"
                )
                continue
            for track in tracks:
                await self._ledger.record_track_result(track)
            await self._ledger.update_position_status(
                position.match_id, PositionStatus.SETTLED
            )
            await self._publish(f"settled:{position.match_id}")
