"""P3 paper ledger transaction repository (T58).

PostgreSQL is the paper authority: intents, fills/no-fills, the single main
position, counterfactual track results and provider resolutions are committed
synchronously with unique idempotency constraints before anything is
published. Every method is safe to replay after a crash or restart; Redis or
browser loss can never create or erase a position.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.markets.models import MarketResolution, OutcomePayout, ResolutionStatus
from app.markets.models import ExecutableQuote
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
from app.persistence.database import Database
from app.persistence.models import (
    MarketResolutionRow,
    PaperFillRow,
    PaperOrderIntentRow,
    PaperPositionRow,
    PaperTrackResultRow,
)


class UniqueViolationError(Exception):
    """A second intent for the same match/side or another uniqueness breach."""


class IllegalLedgerTransitionError(Exception):
    """A backwards or otherwise illegal ledger/resolution transition."""


_POSITION_TRANSITIONS: dict[PositionStatus, frozenset[PositionStatus]] = {
    PositionStatus.OPEN: frozenset(
        {PositionStatus.EXIT_PENDING, PositionStatus.SETTLED}
    ),
    PositionStatus.EXIT_PENDING: frozenset(
        {PositionStatus.EXITED, PositionStatus.EXIT_MISSED}
    ),
    PositionStatus.EXITED: frozenset({PositionStatus.SETTLED}),
    PositionStatus.EXIT_MISSED: frozenset({PositionStatus.SETTLED}),
    PositionStatus.SETTLED: frozenset(),
}


def _intent_from_row(row: PaperOrderIntentRow) -> PaperOrderIntent:
    return PaperOrderIntent(
        id=row.id,
        match_id=row.match_id,
        market_id=row.market_id,
        side=IntentSide(row.side),
        status=IntentStatus(row.status),
        idempotency_key=row.idempotency_key,
        outcome_player_id=row.outcome_player_id,
        stake=row.stake,
        delay_seconds=row.delay_seconds,
        model_version=row.model_version,
        policy_version=row.policy_version,
        rules_hash=row.rules_hash,
        quote=ExecutableQuote.model_validate(row.quote),
        created_at=row.created_at,
        expires_at=row.expires_at,
        no_fill_reason=row.no_fill_reason,
    )


def _position_from_row(row: PaperPositionRow) -> PaperPosition:
    return PaperPosition(
        id=row.id,
        match_id=row.match_id,
        market_id=row.market_id,
        outcome_player_id=row.outcome_player_id,
        entry_cost=row.entry_cost,
        shares=row.shares,
        status=PositionStatus(row.status),
        opened_at=row.opened_at,
        updated_at=row.updated_at,
    )


def _track_from_row(row: PaperTrackResultRow) -> PaperTrackResult:
    return PaperTrackResult(
        match_id=row.match_id,
        position_id=row.position_id,
        track=TrackName(row.track),
        exit_kind=TrackExitKind(row.exit_kind),
        shares=row.shares,
        exit_average_price=row.exit_average_price,
        payout_per_share=row.payout_per_share,
        gross_payout=row.gross_payout,
        net_pnl=row.net_pnl,
        settled_at=row.settled_at,
    )


class PaperLedgerRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_intent(self, intent: PaperOrderIntent) -> PaperOrderIntent:
        """Idempotent by `idempotency_key`; a different key for the same
        match/side raises ``UniqueViolationError`` (one-shot entry/exit)."""
        values: dict[str, Any] = {
            "id": intent.id,
            "match_id": intent.match_id,
            "market_id": intent.market_id,
            "side": intent.side.value,
            "status": IntentStatus.PENDING.value,
            "idempotency_key": intent.idempotency_key,
            "outcome_player_id": intent.outcome_player_id,
            "stake": intent.stake,
            "delay_seconds": intent.delay_seconds,
            "model_version": intent.model_version,
            "policy_version": intent.policy_version,
            "rules_hash": intent.rules_hash,
            "quote": intent.quote.model_dump(mode="json"),
            "created_at": intent.created_at,
            "expires_at": intent.expires_at,
            "no_fill_reason": None,
        }
        statement = pg_insert(PaperOrderIntentRow).values(**values)
        statement = statement.on_conflict_do_nothing(index_elements=["idempotency_key"])
        try:
            async with self._database.session() as session:
                async with session.begin():
                    await session.execute(statement)
        except IntegrityError as exc:
            raise UniqueViolationError(
                f"intent violates one-shot uniqueness for match {intent.match_id} "
                f"side {intent.side.value}"
            ) from exc
        async with self._database.session() as session:
            row = await session.scalar(
                select(PaperOrderIntentRow).where(
                    PaperOrderIntentRow.idempotency_key == intent.idempotency_key
                )
            )
        if row is None:  # pragma: no cover - insert-or-read always yields a row
            raise UniqueViolationError("intent disappeared during creation")
        return _intent_from_row(row)

    async def get_intent(self, intent_id: str) -> PaperOrderIntent | None:
        async with self._database.session() as session:
            row = await session.get(PaperOrderIntentRow, intent_id)
        return _intent_from_row(row) if row is not None else None

    async def load_all_intents(self) -> list[PaperOrderIntent]:
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PaperOrderIntentRow).order_by(
                            PaperOrderIntentRow.created_at
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [_intent_from_row(row) for row in rows]

    async def get_fill_for_intent(self, intent_id: str) -> PaperFill | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(PaperFillRow).where(PaperFillRow.intent_id == intent_id)
            )
        if row is None:
            return None
        return PaperFill(
            intent_id=row.intent_id,
            filled=row.filled,
            shares=row.shares,
            average_price=row.average_price,
            fee=row.fee,
            reason=row.reason,
            executed_book_hash=row.executed_book_hash,
            executed_at=row.executed_at,
        )

    async def record_fill(
        self,
        fill: PaperFill,
        *,
        position: PaperPosition | None = None,
        before_commit: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        """One transaction: fill row + intent status + (entry fill) position.
        Replaying the same fill is a no-op; a failure rolls back completely."""
        async with self._database.session() as session:
            async with session.begin():
                intent_row = await session.get(
                    PaperOrderIntentRow, fill.intent_id, with_for_update=True
                )
                if intent_row is None:
                    raise ValueError(f"unknown intent {fill.intent_id}")
                existing = await session.scalar(
                    select(PaperFillRow.id).where(
                        PaperFillRow.intent_id == fill.intent_id
                    )
                )
                if existing is None:
                    session.add(
                        PaperFillRow(
                            intent_id=fill.intent_id,
                            filled=fill.filled,
                            shares=fill.shares,
                            average_price=fill.average_price,
                            fee=fill.fee,
                            reason=fill.reason if not fill.filled else None,
                            executed_book_hash=fill.executed_book_hash,
                            executed_at=fill.executed_at,
                        )
                    )
                    intent_row.status = (
                        IntentStatus.FILLED.value
                        if fill.filled
                        else IntentStatus.NO_FILL.value
                    )
                    intent_row.no_fill_reason = None if fill.filled else fill.reason
                if (
                    fill.filled
                    and position is not None
                    and intent_row.side == IntentSide.ENTRY.value
                ):
                    position_values = {
                        "id": position.id,
                        "match_id": position.match_id,
                        "market_id": position.market_id,
                        "outcome_player_id": position.outcome_player_id,
                        "entry_cost": position.entry_cost,
                        "shares": position.shares,
                        "status": PositionStatus.OPEN.value,
                        "opened_at": position.opened_at,
                        "updated_at": position.opened_at,
                    }
                    statement = pg_insert(PaperPositionRow).values(**position_values)
                    statement = statement.on_conflict_do_nothing(
                        index_elements=["match_id"]
                    )
                    await session.execute(statement)
                if before_commit is not None:
                    await before_commit(session)

    async def get_position(self, match_id: str) -> PaperPosition | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(PaperPositionRow).where(PaperPositionRow.match_id == match_id)
            )
        return _position_from_row(row) if row is not None else None

    async def update_position_status(
        self,
        match_id: str,
        status: PositionStatus,
        *,
        at: datetime | None = None,
        before_commit: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        """Forward-only status transition; repeating the current status is an
        idempotent no-op. `at` is the ledger event time (defaults to now)."""
        async with self._database.session() as session:
            async with session.begin():
                row = await session.scalar(
                    select(PaperPositionRow)
                    .where(PaperPositionRow.match_id == match_id)
                    .with_for_update()
                )
                if row is None:
                    raise ValueError(f"no paper position for match {match_id}")
                current = PositionStatus(row.status)
                if current is status:
                    return
                if status not in _POSITION_TRANSITIONS[current]:
                    raise IllegalLedgerTransitionError(
                        f"illegal position transition {current.value} -> {status.value}"
                    )
                event_time = at or datetime.now(UTC)
                if event_time < row.opened_at:
                    raise ValueError("position event time precedes opened_at")
                row.status = status.value
                row.updated_at = event_time
                if before_commit is not None:
                    await before_commit(session)

    async def record_track_result(self, result: PaperTrackResult) -> PaperTrackResult:
        """Idempotent per (position, track); first committed result wins."""
        statement = pg_insert(PaperTrackResultRow).values(
            match_id=result.match_id,
            position_id=result.position_id,
            track=result.track.value,
            exit_kind=result.exit_kind.value,
            shares=result.shares,
            exit_average_price=result.exit_average_price,
            payout_per_share=result.payout_per_share,
            gross_payout=result.gross_payout,
            net_pnl=result.net_pnl,
            settled_at=result.settled_at,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=["position_id", "track"]
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)
            row = await session.scalar(
                select(PaperTrackResultRow).where(
                    PaperTrackResultRow.position_id == result.position_id,
                    PaperTrackResultRow.track == result.track.value,
                )
            )
        assert row is not None  # noqa: S101 - insert-or-read always yields a row
        return _track_from_row(row)

    async def load_track_results(self, position_id: str) -> list[PaperTrackResult]:
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PaperTrackResultRow).where(
                            PaperTrackResultRow.position_id == position_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [_track_from_row(row) for row in rows]

    async def record_resolution(self, resolution: MarketResolution) -> None:
        """Upsert the provider resolution; FINAL is terminal and never
        downgrades."""
        payouts = [payout.model_dump(mode="json") for payout in resolution.payouts]
        async with self._database.session() as session:
            async with session.begin():
                existing = await session.get(
                    MarketResolutionRow, resolution.market_id, with_for_update=True
                )
                if (
                    existing is not None
                    and existing.status == ResolutionStatus.FINAL.value
                    and resolution.status is not ResolutionStatus.FINAL
                ):
                    raise IllegalLedgerTransitionError(
                        "final resolution is terminal and cannot downgrade"
                    )
                statement = pg_insert(MarketResolutionRow).values(
                    market_id=resolution.market_id,
                    status=resolution.status.value,
                    rules_version=resolution.rules_version,
                    payouts=payouts,
                    confirmed_at=resolution.confirmed_at,
                    updated_at=datetime.now(UTC),
                )
                statement = statement.on_conflict_do_update(
                    index_elements=["market_id"],
                    set_={
                        "status": statement.excluded.status,
                        "rules_version": statement.excluded.rules_version,
                        "payouts": statement.excluded.payouts,
                        "confirmed_at": statement.excluded.confirmed_at,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
                await session.execute(statement)

    async def get_resolution(self, market_id: str) -> MarketResolution | None:
        async with self._database.session() as session:
            row = await session.get(MarketResolutionRow, market_id)
        if row is None:
            return None
        return MarketResolution(
            market_id=row.market_id,
            status=ResolutionStatus(row.status),
            rules_version=row.rules_version,
            payouts=tuple(OutcomePayout.model_validate(item) for item in row.payouts),
            confirmed_at=row.confirmed_at,
        )

    async def load_pending_intents(self) -> tuple[PaperOrderIntent, ...]:
        """Restart recovery: every intent still awaiting execution."""
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PaperOrderIntentRow)
                        .where(PaperOrderIntentRow.status == IntentStatus.PENDING.value)
                        .order_by(PaperOrderIntentRow.created_at)
                    )
                )
                .scalars()
                .all()
            )
        return tuple(_intent_from_row(row) for row in rows)

    async def load_unsettled_positions(self) -> tuple[PaperPosition, ...]:
        """Restart recovery: every position not yet SETTLED."""
        async with self._database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(PaperPositionRow)
                        .where(PaperPositionRow.status != PositionStatus.SETTLED.value)
                        .order_by(PaperPositionRow.opened_at)
                    )
                )
                .scalars()
                .all()
            )
        return tuple(_position_from_row(row) for row in rows)

    async def count_intents_for_match(self, match_id: str) -> int:
        async with self._database.session() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(PaperOrderIntentRow)
                .where(PaperOrderIntentRow.match_id == match_id)
            )
        return int(count or 0)
