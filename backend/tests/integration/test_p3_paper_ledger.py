"""P3 paper ledger integration against the compose PostgreSQL (T58).

Proves one-shot idempotency, unique per-match intents/positions, full
transactional rollback, restart recovery and provider-final resolution
terminality. Requires compose PostgreSQL + `uv run alembic upgrade head`.
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.config import Settings
from app.markets.models import ResolutionStatus
from app.paper.models import (
    IntentSide,
    IntentStatus,
    PositionStatus,
    TrackName,
)
from app.persistence.database import Database
from app.persistence.market_repositories import MarketRepository
from app.persistence.models import (
    PaperFillRow,
    PaperPositionRow,
    PaperTrackResultRow,
)
from app.persistence.paper_repositories import (
    IllegalLedgerTransitionError,
    PaperLedgerRepository,
    UniqueViolationError,
)
from app.persistence.repositories import PostgresIdentityRepository
from p3_fakes import (
    NOW,
    make_entry_fill,
    make_intent,
    make_market,
    make_position,
    make_resolution,
    make_track_result,
)

pytestmark = pytest.mark.infrastructure


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.paper_order_intents')")
            )
            mapped = result.scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )
    if mapped is None:
        await db.dispose()
        pytest.skip("P3 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


@pytest.fixture()
async def match_id(database: Database) -> str:
    identity = PostgresIdentityRepository(database)
    return await identity.get_or_create("match", "itest-p3p", uuid4().hex[:10])


@pytest.fixture()
async def market_id(database: Database) -> str:
    repository = MarketRepository(database)
    internal_id = await repository.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{uuid4().hex[:8]}",
        condition_id=f"0x{uuid4().hex}",
    )
    await repository.save_market(make_market(internal_id))
    return internal_id


async def test_create_intent_is_idempotent_but_one_per_match_and_side(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    entry = make_intent(match_id, market_id)

    assert await repo.create_intent(entry) == entry
    assert await repo.create_intent(entry) == await repo.create_intent(entry)

    with pytest.raises(UniqueViolationError):
        await repo.create_intent(
            entry.model_copy(
                update={"id": f"int_{uuid4().hex[:12]}", "idempotency_key": "other"}
            )
        )

    # The exit side is the only other intent this match may ever create.
    exit_intent = make_intent(
        match_id, market_id, side=IntentSide.EXIT, idempotency_key=f"exit:{match_id}:v1"
    )
    stored_exit = await repo.create_intent(exit_intent)
    assert stored_exit.side is IntentSide.EXIT
    with pytest.raises(UniqueViolationError):
        await repo.create_intent(
            exit_intent.model_copy(
                update={
                    "id": f"int_{uuid4().hex[:12]}",
                    "idempotency_key": "exit:other",
                }
            )
        )


async def test_entry_fill_creates_exactly_one_position_and_is_idempotent(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    intent = await repo.create_intent(make_intent(match_id, market_id))
    fill = make_entry_fill(intent.id)
    position = make_position(match_id, market_id)

    await repo.record_fill(fill, position=position)
    await repo.record_fill(fill, position=position)

    stored_intent = await repo.get_intent(intent.id)
    assert stored_intent is not None
    assert stored_intent.status is IntentStatus.FILLED

    stored_position = await repo.get_position(match_id)
    assert stored_position == position

    async with database.session() as session:
        fill_count = await session.scalar(
            select(func.count())
            .select_from(PaperFillRow)
            .where(PaperFillRow.intent_id == intent.id)
        )
        position_count = await session.scalar(
            select(func.count())
            .select_from(PaperPositionRow)
            .where(PaperPositionRow.match_id == match_id)
        )
    assert fill_count == 1
    assert position_count == 1


async def test_entry_no_fill_records_reason_and_creates_no_position(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    intent = await repo.create_intent(make_intent(match_id, market_id))

    await repo.record_fill(make_entry_fill(intent.id, filled=False))

    stored_intent = await repo.get_intent(intent.id)
    assert stored_intent is not None
    assert stored_intent.status is IntentStatus.NO_FILL
    assert stored_intent.no_fill_reason == "DEPTH_INSUFFICIENT"
    assert await repo.get_position(match_id) is None


async def test_failed_transition_rolls_back_completely(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    intent = await repo.create_intent(make_intent(match_id, market_id))
    fill = make_entry_fill(intent.id)
    position = make_position(match_id, market_id)

    async def explode(session) -> None:
        raise RuntimeError("interrupted after statements, before commit")

    with pytest.raises(RuntimeError):
        await repo.record_fill(fill, position=position, before_commit=explode)

    stored_intent = await repo.get_intent(intent.id)
    assert stored_intent is not None
    assert stored_intent.status is IntentStatus.PENDING
    assert await repo.get_position(match_id) is None
    async with database.session() as session:
        fill_count = await session.scalar(
            select(func.count())
            .select_from(PaperFillRow)
            .where(PaperFillRow.intent_id == intent.id)
        )
    assert fill_count == 0


async def test_position_status_transitions_are_forward_only_and_idempotent(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    intent = await repo.create_intent(make_intent(match_id, market_id))
    await repo.record_fill(
        make_entry_fill(intent.id), position=make_position(match_id, market_id)
    )

    with pytest.raises(IllegalLedgerTransitionError):
        await repo.update_position_status(match_id, PositionStatus.EXITED)

    # Legal forward path: OPEN -> EXIT_PENDING -> EXIT_MISSED -> SETTLED.
    event_time = NOW + timedelta(hours=3)
    await repo.update_position_status(
        match_id, PositionStatus.EXIT_PENDING, at=event_time
    )
    await repo.update_position_status(
        match_id, PositionStatus.EXIT_PENDING, at=event_time
    )  # idempotent
    await repo.update_position_status(
        match_id, PositionStatus.EXIT_MISSED, at=event_time
    )
    with pytest.raises(IllegalLedgerTransitionError):
        await repo.update_position_status(
            match_id, PositionStatus.EXIT_PENDING, at=event_time
        )
    await repo.update_position_status(match_id, PositionStatus.SETTLED, at=event_time)

    stored = await repo.get_position(match_id)
    assert stored is not None
    assert stored.status is PositionStatus.SETTLED


async def test_track_results_are_unique_per_track(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    intent = await repo.create_intent(make_intent(match_id, market_id))
    position = make_position(match_id, market_id)
    await repo.record_fill(make_entry_fill(intent.id), position=position)

    ev_result = make_track_result(match_id, position.id, track=TrackName.EV_EXIT)
    assert await repo.record_track_result(ev_result) == ev_result
    assert await repo.record_track_result(ev_result) == ev_result

    hodl = make_track_result(match_id, position.id, track=TrackName.HODL_BASELINE)
    await repo.record_track_result(hodl)

    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(PaperTrackResultRow)
            .where(PaperTrackResultRow.position_id == position.id)
        )
    assert count == 2


async def test_final_resolution_is_terminal_and_never_downgrades(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)

    await repo.record_resolution(
        make_resolution(market_id, status=ResolutionStatus.PROPOSED)
    )
    await repo.record_resolution(
        make_resolution(market_id, status=ResolutionStatus.FINAL)
    )

    stored = await repo.get_resolution(market_id)
    assert stored is not None
    assert stored.status is ResolutionStatus.FINAL
    assert stored.confirmed_at is not None
    assert {payout.player_id: payout.payout_per_share for payout in stored.payouts} == {
        "ply_a": Decimal("1"),
        "ply_b": Decimal("0"),
    }

    with pytest.raises(IllegalLedgerTransitionError):
        await repo.record_resolution(
            make_resolution(market_id, status=ResolutionStatus.PROPOSED)
        )


async def test_restart_reloads_pending_intents_and_open_positions(
    database: Database, match_id: str, market_id: str
) -> None:
    repo = PaperLedgerRepository(database)
    pending = await repo.create_intent(make_intent(match_id, market_id))

    other_match_namespace = uuid4().hex[:10]
    identity = PostgresIdentityRepository(database)
    other_match = await identity.get_or_create(
        "match", "itest-p3p", other_match_namespace
    )
    markets = MarketRepository(database)
    other_market = await markets.get_or_create_market_id(
        provider="polymarket",
        provider_event_id=f"ev_{uuid4().hex[:8]}",
        condition_id=f"0x{uuid4().hex}",
    )
    await markets.save_market(make_market(other_market))
    other_intent = await repo.create_intent(make_intent(other_match, other_market))
    other_position = make_position(other_match, other_market)
    await repo.record_fill(make_entry_fill(other_intent.id), position=other_position)

    # Simulate a process restart with a brand new Database instance.
    settings = Settings(_env_file=None)
    restarted = Database(settings.database_url)
    try:
        restarted_repo = PaperLedgerRepository(restarted)
        pending_intents = await restarted_repo.load_pending_intents()
        open_positions = await restarted_repo.load_unsettled_positions()
    finally:
        await restarted.dispose()

    assert pending.id in {intent.id for intent in pending_intents}
    reloaded_pending = next(
        intent for intent in pending_intents if intent.id == pending.id
    )
    assert reloaded_pending == pending
    assert reloaded_pending.quote.average_price == Decimal("0.525")

    assert other_match in {position.match_id for position in open_positions}
    reloaded_position = next(
        position for position in open_positions if position.match_id == other_match
    )
    assert reloaded_position == other_position
