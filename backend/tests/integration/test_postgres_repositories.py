"""P2 repository integration against the compose PostgreSQL.

Requires: `docker compose up -d --wait postgres redis` and
`uv run alembic upgrade head`. Skips honestly when either is missing.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.domain import LiveMatchState, MatchScore
from app.persistence.database import Database
from app.persistence.models import PointEventRevisionRow, PointEventRow
from app.persistence.repositories import (
    MatchSnapshotRepository,
    PostgresIdentityRepository,
    RawProviderEventRepository,
)

pytestmark = pytest.mark.infrastructure

FIXED_NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.match_external_ids')")
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
        pytest.skip("P2 schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        await db.dispose()


def _namespace() -> str:
    return f"itest-{uuid4().hex[:10]}"


def _point_row(match_id: str, point_id: str, sequence: int, fingerprint: str) -> PointEventRow:
    return PointEventRow(
        id=point_id,
        match_id=match_id,
        sequence=sequence,
        set_number=1,
        game_number=1,
        point_number=sequence,
        score_after=MatchScore(
            sets_won=(0, 0), sets=(), points=("15", "0")
        ).model_dump(mode="json"),
        observed_at=FIXED_NOW,
        provider="itest",
        source_fingerprint=fingerprint,
        revision=1,
    )


async def test_concurrent_get_or_create_collapses_to_one_internal_id(
    database: Database,
) -> None:
    repository = PostgresIdentityRepository(database)
    namespace = _namespace()

    results = await asyncio.gather(
        *(repository.get_or_create("match", namespace, "4242") for _ in range(20))
    )

    internal_id = results[0]
    assert set(results) == {internal_id}
    assert internal_id.startswith("mat_")
    assert "4242" not in internal_id
    assert await repository.external_id("match", namespace, internal_id) == "4242"


async def test_identity_is_stable_across_repository_instances(database: Database) -> None:
    namespace = _namespace()
    first = PostgresIdentityRepository(database)
    second = PostgresIdentityRepository(database)

    created = await first.get_or_create("player", namespace, "77")
    reopened = await second.get_or_create("player", namespace, "77")

    assert created == reopened
    assert created.startswith("ply_")
    assert await second.external_id("player", namespace, created) == "77"
    assert await second.external_id("player", namespace, "ply_absent") is None


async def test_entities_keep_distinct_namespaces(database: Database) -> None:
    repository = PostgresIdentityRepository(database)
    namespace = _namespace()

    match_id = await repository.get_or_create("match", namespace, "100")
    player_id = await repository.get_or_create("player", namespace, "100")
    tournament_id = await repository.get_or_create("tournament", namespace, "100")

    assert match_id != player_id
    assert player_id != tournament_id
    assert match_id.startswith("mat_")
    assert player_id.startswith("ply_")
    assert tournament_id.startswith("trn_")


async def test_point_events_reject_duplicate_match_sequence(database: Database) -> None:
    identity = PostgresIdentityRepository(database)
    match_id = await identity.get_or_create("match", _namespace(), "900")

    async with database.session() as session:
        session.add(_point_row(match_id, f"pe_{uuid4().hex}", 1, "fp-1"))
        await session.commit()

    async with database.session() as session:
        session.add(_point_row(match_id, f"pe_{uuid4().hex}", 1, "fp-1-dup"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_point_revisions_append_and_reject_duplicate_revision(
    database: Database,
) -> None:
    identity = PostgresIdentityRepository(database)
    match_id = await identity.get_or_create("match", _namespace(), "901")
    point_id = f"pe_{uuid4().hex}"

    async with database.session() as session:
        session.add(_point_row(match_id, point_id, 1, "fp-a"))
        await session.commit()

    async with database.session() as session:
        session.add(
            PointEventRevisionRow(
                point_event_id=point_id,
                revision=2,
                before_state={"points": ["15", "0"]},
                after_state={"points": ["30", "0"]},
                revised_at=FIXED_NOW + timedelta(minutes=1),
                reason="provider_correction",
            )
        )
        await session.commit()

    async with database.session() as session:
        session.add(
            PointEventRevisionRow(
                point_event_id=point_id,
                revision=2,
                before_state={"points": ["15", "0"]},
                after_state={"points": ["40", "0"]},
                revised_at=FIXED_NOW + timedelta(minutes=2),
                reason="duplicate",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

    async with database.session() as session:
        rows = (
            await session.execute(
                select(PointEventRevisionRow).where(
                    PointEventRevisionRow.point_event_id == point_id
                )
            )
        ).scalars().all()
    assert [row.revision for row in rows] == [2]
    assert rows[0].after_state == {"points": ["30", "0"]}


async def test_snapshot_repository_keeps_single_current_state(database: Database) -> None:
    identity = PostgresIdentityRepository(database)
    match_id = await identity.get_or_create("match", _namespace(), "902")
    repository = MatchSnapshotRepository(database)

    state_v1 = LiveMatchState(
        score=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
        state_version=1,
        connection_status="live",
        as_of=FIXED_NOW,
    )
    state_v2 = LiveMatchState(
        score=MatchScore(sets_won=(0, 0), sets=(), points=("30", "0")),
        state_version=2,
        connection_status="live",
        as_of=FIXED_NOW + timedelta(minutes=1),
    )

    await repository.save_current_state(match_id=match_id, live_state=state_v1, as_of=FIXED_NOW)
    await repository.save_current_state(
        match_id=match_id,
        live_state=state_v2,
        as_of=FIXED_NOW + timedelta(minutes=1),
    )

    current = await repository.get_current_state(match_id)
    assert current is not None
    state, as_of = current
    assert state.state_version == 2
    assert state.score is not None and state.score.points == ("30", "0")
    assert as_of == FIXED_NOW + timedelta(minutes=1)

    assert await repository.get_current_state("mat_absent") is None


async def test_raw_purge_deletes_only_before_cutoff_and_keeps_canonical(
    database: Database,
) -> None:
    identity = PostgresIdentityRepository(database)
    namespace = _namespace()
    match_id = await identity.get_or_create("match", namespace, "903")
    external_match_id = f"raw-{uuid4().hex[:10]}"
    raw = RawProviderEventRepository(database)

    old_at = FIXED_NOW - timedelta(days=15)
    boundary_at = FIXED_NOW - timedelta(days=14)
    fresh_at = FIXED_NOW - timedelta(days=1)

    await raw.append(
        external_match_id=external_match_id,
        provider="itest",
        channel="websocket",
        kind="snapshot",
        payload={"seq": "old"},
        observed_at=old_at,
    )
    await raw.append(
        external_match_id=external_match_id,
        provider="itest",
        channel="websocket",
        kind="snapshot",
        payload={"seq": "boundary"},
        observed_at=boundary_at,
    )
    await raw.append(
        external_match_id=external_match_id,
        provider="itest",
        channel="websocket",
        kind="snapshot",
        payload={"seq": "fresh"},
        observed_at=fresh_at,
    )

    point_id = f"pe_{uuid4().hex}"
    async with database.session() as session:
        session.add(_point_row(match_id, point_id, 1, "fp-keep"))
        await session.commit()

    deleted = await raw.purge_raw_events(FIXED_NOW - timedelta(days=14))
    assert deleted >= 1

    remaining = await raw.read_for_external_match(external_match_id)
    assert [event.payload["seq"] for event in remaining] == ["boundary", "fresh"]

    async with database.session() as session:
        kept = (
            await session.execute(select(PointEventRow).where(PointEventRow.id == point_id))
        ).scalar_one_or_none()
    assert kept is not None
    assert kept.source_fingerprint == "fp-keep"
