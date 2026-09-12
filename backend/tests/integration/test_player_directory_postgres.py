"""Player directory persistence against the compose PostgreSQL.

Requires: `docker compose up -d --wait postgres redis` and
`uv run alembic upgrade head`. Skips honestly when either is missing.
"""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.config import Settings
from app.domain import LiveMatchState, Player
from app.persistence.database import Database
from app.persistence.models import MatchRow, PlayerRow
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import (
    MatchSnapshotRepository,
    PostgresIdentityRepository,
)
from app.players.models import (
    LocalizedNameUpdate,
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
    RankingEntry,
    RankingMovement,
    Tour,
)

pytestmark = pytest.mark.infrastructure

FIXED_NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)
# Ranking snapshots written by tests use a dedicated synthetic future date:
# always the latest snapshot for assertions, never colliding with real syncs.
TEST_RANKING_DATE = date(2030, 1, 5)


@pytest.fixture()
async def database():
    settings = Settings(_env_file=None)
    db = Database(settings.database_url)
    try:
        async with db.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT to_regclass('public.player_aliases')")
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
        pytest.skip("player directory schema not migrated; run `uv run alembic upgrade head`")
    try:
        yield db
    finally:
        # Tests write only into the `dir-` namespace (names and external IDs);
        # identity-generated internal IDs are random, so clean via both keys.
        # The data-mutating CTE drops external mappings and their players in a
        # single statement because the two tables reference each other.
        async with db.session() as session:
            async with session.begin():
                await session.execute(
                    text("DELETE FROM match_state_snapshots WHERE match_id LIKE 'mat_dir-%'")
                )
                await session.execute(
                    text("DELETE FROM match_external_ids WHERE internal_id LIKE 'mat_dir-%'")
                )
                await session.execute(
                    text("DELETE FROM matches WHERE id LIKE 'mat_dir-%'")
                )
                await session.execute(
                    text(
                        "DELETE FROM player_aliases WHERE player_id IN "
                        "(SELECT id FROM players WHERE name LIKE 'dir-%') OR player_id IN "
                        "(SELECT internal_id FROM player_external_ids WHERE external_id LIKE 'dir-%')"
                    )
                )
                await session.execute(
                    text(
                        "DELETE FROM player_rankings WHERE player_id IN "
                        "(SELECT id FROM players WHERE name LIKE 'dir-%') OR player_id IN "
                        "(SELECT internal_id FROM player_external_ids WHERE external_id LIKE 'dir-%')"
                    )
                )
                await session.execute(
                    text(
                        "DELETE FROM player_external_ids WHERE internal_id IN "
                        "(SELECT id FROM players WHERE name LIKE 'dir-%')"
                    )
                )
                await session.execute(
                    text(
                        "WITH gone AS ("
                        "DELETE FROM player_external_ids WHERE external_id LIKE 'dir-%' "
                        "RETURNING internal_id) "
                        "DELETE FROM players WHERE id IN (SELECT internal_id FROM gone) "
                        "OR name LIKE 'dir-%'"
                    )
                )
        await db.dispose()


def _namespace() -> str:
    return f"dir-{uuid4().hex[:10]}"


def _entry(namespace: str, index: int, tour: Tour, rank: int, *, country: str = "ita") -> RankingEntry:
    return RankingEntry(
        player=Player(
            id=f"ply_{namespace}_{index}",
            name=f"{namespace} Player {index}",
            country_code=country,
            ranking=rank,
        ),
        tour=tour,
        rank=rank,
        points=1000 - index,
        movement=RankingMovement.SAME,
        ranking_date=TEST_RANKING_DATE,
        fetched_at=FIXED_NOW,
    )


def _alias(player_id: str, normalized: str, kind: PlayerAliasKind) -> PlayerAlias:
    return PlayerAlias(
        player_id=player_id,
        locale="en",
        alias=normalized,
        normalized_alias=normalized,
        kind=kind,
        source=PlayerAliasSource.DERIVED,
    )


@pytest.mark.asyncio
async def test_ranking_snapshot_roundtrip_with_country_filter_and_pagination(
    database: Database,
) -> None:
    repository = PostgresPlayerDirectoryRepository(database)
    namespace = _namespace()
    snapshot = tuple(
        _entry(namespace, index, Tour.ATP, index, country="chn" if index % 2 == 0 else "ita")
        for index in range(1, 121)
    )
    await repository.save_ranking_snapshot(snapshot)

    chinese, total = await repository.get_rankings(Tour.ATP, page=1, page_size=50, country_code="chn")
    assert total == 60
    assert len(chinese) == 50
    assert all(item.player.country_code == "chn" for item in chinese)

    page3, total = await repository.get_rankings(Tour.ATP, page=3, page_size=50, country_code=None)
    assert total == 120
    assert page3[0].rank == 101

    player = await repository.get_player(f"ply_{namespace}_1")
    assert player is not None
    assert player.player.localized_name is None


@pytest.mark.asyncio
async def test_alias_idempotency_and_ambiguity(database: Database) -> None:
    repository = PostgresPlayerDirectoryRepository(database)
    namespace = _namespace()
    await repository.save_ranking_snapshot(
        (
            _entry(namespace, 1, Tour.ATP, 10),
            _entry(namespace, 2, Tour.WTA, 20),
        )
    )

    first = await repository.upsert_aliases(
        (
            _alias(f"ply_{namespace}_1", f"{namespace} wang", PlayerAliasKind.SURNAME),
            _alias(f"ply_{namespace}_2", f"{namespace} wang", PlayerAliasKind.SURNAME),
        )
    )
    second = await repository.upsert_aliases(
        (
            _alias(f"ply_{namespace}_1", f"{namespace} wang", PlayerAliasKind.SURNAME),
            _alias(f"ply_{namespace}_2", f"{namespace} wang", PlayerAliasKind.SURNAME),
        )
    )
    assert first == 2
    assert second == 0

    matches = await repository.find_aliases(f"{namespace} wang", limit=10)
    assert {item.player.player.id for item in matches} == {
        f"ply_{namespace}_1",
        f"ply_{namespace}_2",
    }


@pytest.mark.asyncio
async def test_save_localized_names_is_atomic(database: Database) -> None:
    repository = PostgresPlayerDirectoryRepository(database)
    namespace = _namespace()
    await repository.save_ranking_snapshot((_entry(namespace, 1, Tour.ATP, 1),))

    from app.errors import AppError

    with pytest.raises(AppError):
        await repository.save_localized_names(
            (
                LocalizedNameUpdate(
                    player_id=f"ply_{namespace}_1", localized_name="本地名", aliases=()
                ),
                LocalizedNameUpdate(
                    player_id=f"ply_{namespace}_missing", localized_name="不存在", aliases=()
                ),
            )
        )

    untouched = await repository.get_player(f"ply_{namespace}_1")
    assert untouched is not None
    assert untouched.player.localized_name is None

    written = await repository.save_localized_names(
        (
            LocalizedNameUpdate(
                player_id=f"ply_{namespace}_1",
                localized_name="本地名",
                aliases=(_alias(f"ply_{namespace}_1", f"{namespace} 本地名", PlayerAliasKind.PREFERRED),),
            ),
        )
    )
    assert written == 1
    localized = await repository.get_player(f"ply_{namespace}_1")
    assert localized is not None
    assert localized.player.localized_name == "本地名"
    matches = await repository.find_aliases(f"{namespace} 本地名", limit=5)
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_concurrent_external_ids_converge_to_one_directory_player(
    database: Database,
) -> None:
    identities = PostgresIdentityRepository(database)
    repository = PostgresPlayerDirectoryRepository(database)
    namespace = _namespace()
    external = f"{namespace}-external"

    internal_ids = await asyncio.gather(
        *(identities.get_or_create("player", "api_tennis", external) for _ in range(20))
    )
    assert len(set(internal_ids)) == 1
    internal_id = internal_ids[0]

    await repository.save_ranking_snapshot(
        (
            RankingEntry(
                player=Player(id=internal_id, name=f"{namespace} Converged", ranking=77),
                tour=Tour.ATP,
                rank=77,
                points=777,
                movement=RankingMovement.SAME,
                ranking_date=TEST_RANKING_DATE,
                fetched_at=FIXED_NOW,
            ),
        )
    )

    async with database.session() as session:
        rows = (
            await session.execute(select(PlayerRow).where(PlayerRow.id == internal_id))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == f"{namespace} Converged"


@pytest.mark.asyncio
async def test_match_snapshot_rebuild_carries_localized_name(database: Database) -> None:
    identities = PostgresIdentityRepository(database)
    repository = PostgresPlayerDirectoryRepository(database)
    snapshots = MatchSnapshotRepository(database)
    namespace = _namespace()

    first_id = await identities.get_or_create("player", "api_tennis", f"{namespace}-p1")
    second_id = await identities.get_or_create("player", "api_tennis", f"{namespace}-p2")
    tournament_id = await identities.get_or_create("tournament", "api_tennis", f"{namespace}-t")
    match_id = f"mat_{namespace}_1"

    await repository.save_ranking_snapshot(
        (
            RankingEntry(
                player=Player(id=first_id, name=f"{namespace} One", ranking=1),
                tour=Tour.ATP,
                rank=1,
                points=100,
                movement=RankingMovement.SAME,
                ranking_date=TEST_RANKING_DATE,
                fetched_at=FIXED_NOW,
            ),
        )
    )
    await repository.save_localized_names(
        (LocalizedNameUpdate(player_id=first_id, localized_name="第一名", aliases=()),)
    )

    async with database.session() as session:
        async with session.begin():
            # The tournament row already exists via identity get_or_create;
            # only the match row is new here.
            session.add(
                MatchRow(
                    id=match_id,
                    status="live",
                    player1_id=first_id,
                    player2_id=second_id,
                    tournament_id=tournament_id,
                )
            )
    await snapshots.save_current_state(
        match_id=match_id, live_state=LiveMatchState(), as_of=FIXED_NOW
    )

    snapshot = await snapshots.load_snapshot(match_id)
    assert snapshot is not None
    assert snapshot.match.players[0].localized_name == "第一名"
    assert snapshot.match.players[1].localized_name is None
