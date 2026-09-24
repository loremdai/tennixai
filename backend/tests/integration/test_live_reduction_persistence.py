"""Transactional persistence of live reductions against compose PostgreSQL."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.domain import (
    CapabilityStatus,
    CircuitTier,
    DataFreshness,
    DataQuality,
    Discipline,
    Gender,
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
    MomentumObservationRow,
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
        score_before=MatchScore(
            sets_won=(0, 0),
            sets=(SetScore(number=3, player1_games=2, player2_games=2),),
            points=("0", "0"),
        ),
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=score_after),
        is_set_point=False,
        is_match_point=True,
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
        players=(
            Player(id="ply_a", name="A", localized_name="甲", country_code="chn"),
            Player(id="ply_b", name="B", localized_name="乙", country_code="jpn"),
        ),
        tournament=Tournament(
            id="trn_a",
            name="T",
            tour="atp",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=NOW + timedelta(days=1),
        round="Round of 32",
        surface="hard",
        indoor=True,
        format="BO3",
        live_state=LiveMatchState(
            current_set_number=3,
            score=MatchScore(
                sets_won=(1, 1),
                sets=(SetScore(number=3, player1_games=2, player2_games=2),),
                points=("30", "15"),
            ),
            server_player_id="ply_a",
            state_version=0,
        ),
        freshness=DataFreshness(
            provider="api_tennis",
            source_updated_at=NOW - timedelta(seconds=15),
            observed_at=NOW,
        ),
    )
    return MatchSnapshot(
        match=match,
        points=tuple(point(match_id, i, ("15", "0")) for i in range(1, points + 1)),
        statistics=(statistic(match_id, aces),),
        momentum=(),
        quality=(
            DataQuality(
                capability="statistics",
                status=CapabilityStatus.AVAILABLE,
                provider="api_tennis",
                observed_at=NOW,
            ),
        ),
        state_version=0,
        as_of=NOW,
    )


async def test_load_snapshot_rebuilds_the_canonical_view(database: Database) -> None:
    repository = MatchSnapshotRepository(database)
    source = await candidate(database, points=2, aces=4)
    indeterminate = source.points[0].model_copy(
        update={
            "winner_player_id": None,
            "quality": DataQuality(
                capability="point_winner",
                status=CapabilityStatus.PARTIAL,
                provider="api_tennis",
                reason="winner_indeterminate",
                observed_at=NOW,
            ),
        }
    )
    source = source.model_copy(
        update={"points": (indeterminate, *source.points[1:])}
    )
    reduction = reduce_live_snapshot(None, source)
    await repository.save_reduction(reduction)

    loaded = await repository.load_snapshot(reduction.match_id)

    assert loaded is not None
    assert loaded.match.live_state is not None
    assert loaded.match.live_state.current_set_number == 3
    assert loaded.state_version == reduction.snapshot.state_version
    assert [point.sequence for point in loaded.points] == [1, 2]
    assert loaded.points[0].winner_player_id is None
    assert loaded.points[0].score_before == reduction.snapshot.points[0].score_before
    assert loaded.points[0].score_after == reduction.snapshot.points[0].score_after
    assert loaded.points[0].is_break_point is None
    assert loaded.points[0].is_set_point is False
    assert loaded.points[0].is_match_point is True
    assert loaded.points[0].observed_at == NOW
    assert loaded.points[0].provider == "itest"
    assert loaded.points[0].source_fingerprint == "fp-1"
    assert loaded.points[0].revision == 1
    assert loaded.points[0].quality == reduction.snapshot.points[0].quality
    aces = next(stat for stat in loaded.statistics if stat.name is StatisticName.ACES)
    assert aces.player1_value == 4
    assert aces.player2_value == 1
    assert aces.unit == "count"
    assert aces.provenance is StatisticProvenance.PROVIDER
    assert aces.availability is CapabilityStatus.AVAILABLE
    assert aces.as_of == NOW
    assert loaded.match.players[0].id == "ply_a"
    assert loaded.match.players[0].localized_name == "甲"
    assert loaded.match.players[0].country_code == "chn"
    assert loaded.match.players[0].ranking is None
    assert loaded.match.tournament == reduction.snapshot.match.tournament
    assert loaded.match.scheduled_at == NOW + timedelta(days=1)
    assert loaded.match.round == "Round of 32"
    assert loaded.match.surface == "hard"
    assert loaded.match.indoor is True
    assert loaded.match.format == "BO3"
    assert loaded.match.freshness == reduction.snapshot.match.freshness
    assert loaded.match.live_state is not None
    assert loaded.match.live_state == reduction.snapshot.match.live_state
    assert loaded.match.live_state.state_version == loaded.state_version
    assert len(loaded.momentum) == 1
    assert all(item.state_version == loaded.state_version for item in loaded.momentum)
    assert loaded.momentum == reduction.snapshot.momentum
    assert loaded.quality == reduction.snapshot.quality
    assert loaded.as_of == reduction.snapshot.as_of


async def test_legacy_snapshot_without_freshness_reports_unknown_provider(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    reduction = reduce_live_snapshot(None, await candidate(database))
    await repository.save_reduction(reduction)

    async with database.session() as session:
        await session.execute(
            update(MatchStateSnapshotRow)
            .where(MatchStateSnapshotRow.match_id == reduction.match_id)
            .values(freshness=None)
        )
        await session.commit()

    loaded = await repository.load_snapshot(reduction.match_id)

    assert loaded is not None
    assert loaded.match.freshness.provider == "unknown"
    assert loaded.match.freshness.observed_at == loaded.as_of


async def test_save_reduction_upserts_and_replays_momentum_observations(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    base = await candidate(database, points=4)
    first = reduce_live_snapshot(None, base)
    await repository.save_reduction(first)

    corrected_last = base.points[-1].model_copy(
        update={"winner_player_id": "ply_b", "source_fingerprint": "fp-4-fixed"}
    )
    second_candidate = base.model_copy(
        update={"points": (*base.points[:-1], corrected_last)}
    )
    second = reduce_live_snapshot(first.snapshot, second_candidate)
    await repository.save_reduction(second)

    async with database.session() as session:
        rows = (
            await session.execute(
                select(MomentumObservationRow)
                .where(MomentumObservationRow.match_id == base.match.id)
                .order_by(MomentumObservationRow.point_sequence)
            )
        ).scalars().all()

    loaded = await repository.load_snapshot(base.match.id)
    assert loaded is not None
    assert [row.point_sequence for row in rows] == [1, 2, 3, 4]
    assert [item.point_sequence for item in loaded.momentum] == [1, 2, 3, 4]
    assert rows[-1].state_version == second.snapshot.state_version
    assert rows[-1].value == pytest.approx(second.snapshot.momentum[-1].value)


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


async def test_save_reduction_handles_resequenced_point_ids(database: Database) -> None:
    repository = MatchSnapshotRepository(database)
    base = await candidate(database, points=3)
    first = reduce_live_snapshot(None, base)
    await repository.save_reduction(first)

    extra = point(base.match.id, 4, ("30", "15"), winner="ply_b")
    reordered = base.model_copy(
        update={"points": (base.points[0], base.points[2], extra)}
    )
    second = reduce_live_snapshot(first.snapshot, reordered)

    await repository.save_reduction(second)

    loaded = await repository.load_snapshot(base.match.id)
    assert loaded is not None
    assert [item.sequence for item in loaded.points] == [1, 2, 3]


async def test_save_reduction_handles_inserted_supplier_point_id_collision(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    base = await candidate(database, points=3)
    first = reduce_live_snapshot(None, base)
    await repository.save_reduction(first)

    inserted = point(base.match.id, 4, ("30", "15"), winner="ply_b").model_copy(
        update={"id": first.snapshot.points[1].id}
    )
    second_candidate = base.model_copy(
        update={
            "points": (base.points[0], base.points[1], inserted, base.points[2]),
        }
    )
    second = reduce_live_snapshot(first.snapshot, second_candidate)

    await repository.save_reduction(second)

    loaded = await repository.load_snapshot(base.match.id)
    assert loaded is not None
    assert [item.sequence for item in loaded.points] == [1, 2, 3, 4]
    assert len({item.id for item in loaded.points}) == 4


async def test_save_reduction_handles_moved_tail_id_at_new_sequence(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    base = await candidate(database, points=3)
    first = reduce_live_snapshot(None, base)
    await repository.save_reduction(first)

    inserted_before_tail = point(
        base.match.id, 4, ("30", "15"), winner="ply_b"
    ).model_copy(update={"id": first.snapshot.points[1].id})
    inserted_before_tail_again = point(
        base.match.id, 5, ("40", "15"), winner="ply_b"
    ).model_copy(update={"id": first.snapshot.points[2].id})
    reordered = base.model_copy(
        update={
            "points": (
                base.points[0],
                inserted_before_tail,
                inserted_before_tail_again,
                base.points[2],
            ),
        }
    )
    second = reduce_live_snapshot(first.snapshot, reordered)

    await repository.save_reduction(second)

    loaded = await repository.load_snapshot(base.match.id)
    assert loaded is not None
    assert [item.sequence for item in loaded.points] == [1, 2, 3, 4]
    assert len({item.id for item in loaded.points}) == 4


async def test_failed_reduction_save_leaves_previous_version_readable(
    database: Database,
) -> None:
    repository = MatchSnapshotRepository(database)
    first = reduce_live_snapshot(None, await candidate(database))
    await repository.save_reduction(first)

    async def violate_foreign_key(session) -> None:
        session.add(
            PointEventRow(
                id="pe_boom",
                match_id="mat_no_such_match",
                sequence=99,
                set_number=1,
                game_number=1,
                point_number=1,
                score_after={"sets_won": [0, 0], "sets": [], "points": ["15", "0"], "is_tiebreak": False},
                observed_at=NOW,
                provider="itest",
                source_fingerprint="boom",
                revision=1,
            )
        )
        await session.flush()

    with pytest.raises(IntegrityError):
        await repository.save_reduction(first, before_commit=violate_foreign_key)

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
        boom = (
            await session.execute(
                select(PointEventRow).where(PointEventRow.id == "pe_boom")
            )
        ).scalar_one_or_none()
    assert len(points) == 3
    assert boom is None
