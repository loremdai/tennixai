"""Transactional persistence of live reductions against compose PostgreSQL."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.domain import (
    CapabilityStatus,
    DataFreshness,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    MatchStatus,
    Player,
    PointEvent,
    SetScore,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.persistence.database import Database
from app.persistence.models import (
    MatchStateSnapshotRow,
    MatchStatisticRow,
    PointEventRevisionRow,
    PointEventRow,
)
from app.persistence.repositories import (
    MatchSnapshotRepository,
    PostgresIdentityRepository,
)
from app.realtime.reducer import reduce_live_snapshot

pytestmark = pytest.mark.infrastructure

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.match_state_snapshots')")
            )
            mapped = result.scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        await db.dispose()
        pytest.skip(
            f"PostgreSQL not reachable at TENNIX_DATABASE_URL ({type(exc).__name__})"
        )
    if mapped is None:
        await db.dispose()
        pytest.skip("P2 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


def point(match_id: str, sequence: int, score_after: tuple[str, str], winner: str = "ply_a") -> PointEvent:
    return PointEvent(
        id=f"pe_{match_id}_{sequence}",
        match_id=match_id,
        sequence=sequence,
        set_number=3,
        game_number=1,
        point_number=sequence,
        server_player_id="ply_a",
        winner_player_id=winner,
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=score_after),
        observed_at=NOW,
        provider="itest",
        source_fingerprint=f"fp-{sequence}",
        revision=1,
    )


def statistic(match_id: str, aces_p1: float) -> MatchStatistic:
    return MatchStatistic(
        match_id=match_id,
        name=StatisticName.ACES,
        period="match",
        player1_value=aces_p1,
        player2_value=1,
        unit="count",
        provenance=StatisticProvenance.PROVIDER,
        availability=CapabilityStatus.AVAILABLE,
        as_of=NOW,
    )


async def candidate(database: Database, *, points: int = 3, aces: float = 2) -> MatchSnapshot:
    identity = PostgresIdentityRepository(database)
    namespace = f"reducer-{uuid4().hex[:8]}"
    match_id = await identity.get_or_create("match", namespace, "777001")
    match = Match(
        id=match_id,
        status=MatchStatus.LIVE,
        players=(Player(id="ply_a", name="A"), Player(id="ply_b", name="B")),
        tournament=Tournament(id="trn_a", name="T"),
        live_state=LiveMatchState(
            score=MatchScore(
                sets_won=(1, 1),
                sets=(SetScore(number=3, player1_games=2, player2_games=2),),
                points=("30", "15"),
            ),
            server_player_id="ply_a",
            state_version=0,
        ),
        freshness=DataFreshness(provider="itest", observed_at=NOW),
    )
    return MatchSnapshot(
        match=match,
        points=tuple(point(match_id, i, ("15", "0")) for i in range(1, points + 1)),
        statistics=(statistic(match_id, aces),),
        momentum=(),
        quality=(),
        state_version=0,
        as_of=NOW,
    )


async def test_save_reduction_writes_snapshot_points_and_statistics(database: Database) -> None:
    repository = MatchSnapshotRepository(database)
    reduction = reduce_live_snapshot(None, await candidate(database))

    await repository.save_reduction(reduction)

    async with database.session() as session:
        snapshot_row = (
            await session.execute(
                select(MatchStateSnapshotRow).where(
                    MatchStateSnapshotRow.match_id == reduction.match_id
                )
            )
        ).scalar_one()
        points = (
            await session.execute(
                select(PointEventRow).where(PointEventRow.match_id == reduction.match_id)
            )
        ).scalars().all()
        stats = (
            await session.execute(
                select(MatchStatisticRow).where(
                    MatchStatisticRow.match_id == reduction.match_id
                )
            )
        ).scalars().all()

    assert snapshot_row.state_version == reduction.snapshot.state_version == 1
    assert len(points) == 3
    assert [row.sequence for row in points] == [1, 2, 3]
    assert len(stats) == 1
    assert stats[0].player1_value == 2


async def test_saving_the_same_reduction_twice_is_idempotent(database: Database) -> None:
    repository = MatchSnapshotRepository(database)
    reduction = reduce_live_snapshot(None, await candidate(database))

    await repository.save_reduction(reduction)
    await repository.save_reduction(reduction)

    async with database.session() as session:
        points = (
            await session.execute(
                select(PointEventRow).where(PointEventRow.match_id == reduction.match_id)
            )
        ).scalars().all()
        revisions = (
            await session.execute(
                select(PointEventRevisionRow).where(
                    PointEventRevisionRow.point_event_id.in_(
                        [row.id for row in points]
                    )
                )
            )
        ).scalars().all()

    assert len(points) == 3
    assert revisions == []


async def test_second_reduction_appends_point_and_records_revision(database: Database) -> None:
    repository = MatchSnapshotRepository(database)
    base = await candidate(database)
    first = reduce_live_snapshot(None, base)
    await repository.save_reduction(first)

    corrected_last = base.points[-1].model_copy(
        update={"winner_player_id": "ply_b", "source_fingerprint": "fp-3-fixed"}
    )
    extra = point(base.match.id, 4, ("30", "15"), winner="ply_b")
    second_candidate = base.model_copy(
        update={
            "points": (*base.points[:-1], corrected_last, extra),
            "statistics": (statistic(base.match.id, 5),),
        }
    )
    second = reduce_live_snapshot(first.snapshot, second_candidate)
    assert second.snapshot.state_version == 2

    await repository.save_reduction(second)

    async with database.session() as session:
        points = (
            await session.execute(
                select(PointEventRow)
                .where(PointEventRow.match_id == base.match.id)
                .order_by(PointEventRow.sequence)
            )
        ).scalars().all()
        revisions = (
            await session.execute(
                select(PointEventRevisionRow).where(
                    PointEventRevisionRow.point_event_id.in_([row.id for row in points])
                )
            )
        ).scalars().all()
        stats = (
            await session.execute(
                select(MatchStatisticRow).where(
                    MatchStatisticRow.match_id == base.match.id
                )
            )
        ).scalars().all()
        snapshot_row = (
            await session.execute(
                select(MatchStateSnapshotRow).where(
                    MatchStateSnapshotRow.match_id == base.match.id
                )
            )
        ).scalar_one()

    assert [row.sequence for row in points] == [1, 2, 3, 4]
    assert points[2].revision == 2
    assert points[2].winner_player_id == "ply_b"
    assert len(revisions) == 1
    assert revisions[0].revision == 2
    assert stats[0].player1_value == 5
    assert snapshot_row.state_version == 2


async def test_failed_reduction_save_leaves_previous_version_readable(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    first = reduce_live_snapshot(None, await candidate(database))
    await repository.save_reduction(first)

    foreign = first.snapshot.model_copy(
        update={
            "match": first.snapshot.match.model_copy(update={"id": "mat_missing_fk"}),
        }
    )
    broken = first.model_copy(
        update={"match_id": "mat_missing_fk", "snapshot": foreign}
    )

    with pytest.raises(IntegrityError):
        await repository.save_reduction(broken)

    current = await repository.get_current_state(first.match_id)
    assert current is not None
    state, _ = current
    assert state.state_version == first.snapshot.state_version

    async with database.session() as session:
        points = (
            await session.execute(
                select(PointEventRow).where(PointEventRow.match_id == first.match_id)
            )
        ).scalars().all()
    assert len(points) == 3
