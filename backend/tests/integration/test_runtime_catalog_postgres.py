"""P4.1 runtime catalog and state integration (T74).

Runs against a dedicated scratch database (``tennix_runtime_test``) on the
compose PostgreSQL server; the legacy ``tennix`` database, the live-local
database and the P3 shadow preview are never touched. The session fixture
recreates the scratch database and migrates it to head, so every run starts
pristine; no test ever deletes existing P2/P3 rows.
"""

import asyncio
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Gender,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.persistence.database import Database
from app.persistence.models import MarketRow, MatchRow, PlayerRow, RawProviderEventRow
from app.persistence.repositories import (
    CATALOG_FRESHNESS_PROVIDER,
    MatchCatalogRepository,
    RuntimeStateRepository,
)
from app.runtime.models import (
    RuntimeHealth,
    RuntimeInitRecord,
    RuntimeSourceHealth,
    RuntimeSourceStatus,
)

pytestmark = pytest.mark.infrastructure

SCRATCH_DATABASE_NAME = "tennix_runtime_test"
_PROTECTED_DATABASES = frozenset(
    {"postgres", "tennix", "tennix_live_local", "tennix_p3_shadow_preview"}
)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)


def _base_url():
    return make_url(Settings(_env_file=None).database_url)


def _scratch_url() -> str:
    return (
        _base_url()
        .set(database=SCRATCH_DATABASE_NAME)
        .render_as_string(hide_password=False)
    )


def _admin_dsn(database: str) -> str:
    url = _base_url()
    return (
        f"postgresql://{url.username}:{quote_plus(url.password or '')}"
        f"@{url.host}:{url.port}/{database}"
    )


def _recreate_scratch_database() -> None:
    """Drop, recreate and migrate the scratch database (never a protected one)."""
    assert SCRATCH_DATABASE_NAME not in _PROTECTED_DATABASES
    assert _base_url().database != SCRATCH_DATABASE_NAME

    async def _recreate() -> None:
        connection = await asyncpg.connect(_admin_dsn("postgres"))
        try:
            await connection.execute(
                f"DROP DATABASE IF EXISTS {SCRATCH_DATABASE_NAME} WITH (FORCE)"
            )
            await connection.execute(f"CREATE DATABASE {SCRATCH_DATABASE_NAME}")
        finally:
            await connection.close()

    try:
        asyncio.run(_recreate())
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )
    env = {**os.environ, "TENNIX_DATABASE_URL": _scratch_url()}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def scratch_database_url() -> str:
    _recreate_scratch_database()
    return _scratch_url()


@pytest.fixture()
async def database(scratch_database_url: str):
    db = Database(scratch_database_url)
    try:
        yield db
    finally:
        await db.dispose()


def _internal_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _make_match(
    *,
    status: MatchStatus,
    scheduled_at: datetime,
    winner_player_id: str | None = None,
) -> Match:
    return Match(
        id=_internal_id("mat"),
        status=status,
        players=(
            Player(
                id=_internal_id("ply"),
                name="Isolated Player One",
                country_code="aus",
                ranking=12,
            ),
            Player(
                id=_internal_id("ply"),
                name="Isolated Player Two",
                localized_name="隔离选手二",
                country_code="chn",
                ranking=34,
            ),
        ),
        tournament=Tournament(
            id=_internal_id("trn"),
            name="Isolated Open",
            circuit=CircuitTier.ATP,
            gender=Gender.MEN,
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=scheduled_at,
        round="R16",
        surface="hard",
        indoor=False,
        format="best_of_3",
        winner_player_id=winner_player_id,
        freshness=DataFreshness(provider=CATALOG_FRESHNESS_PROVIDER, observed_at=NOW),
    )


@pytest.fixture()
def upcoming_match() -> Match:
    return _make_match(
        status=MatchStatus.SCHEDULED, scheduled_at=NOW + timedelta(hours=3)
    )


def _health(generated_at: datetime = NOW) -> RuntimeHealth:
    return RuntimeHealth(
        generated_at=generated_at,
        sources={
            "live_catalog": RuntimeSourceHealth(
                status=RuntimeSourceStatus.OK,
                last_success_at=generated_at,
                success_count=1,
            )
        },
    )


async def test_catalog_round_trips_scheduled_match_without_live_snapshot(
    database: Database, upcoming_match: Match
) -> None:
    catalog = MatchCatalogRepository(database)
    inserted = await catalog.upsert_matches([upcoming_match], observed_at=NOW)
    assert inserted == {upcoming_match.players[0].id, upcoming_match.players[1].id}
    # The scratch database persists across tests within a session, so the
    # round-trip is scoped to this match's player; the assertion is the
    # brief's exact-equality contract.
    listed = await catalog.list_matches(
        MatchStatus.SCHEDULED, player_id=upcoming_match.players[0].id
    )
    assert listed == [upcoming_match]
    assert listed[0].live_state is None
    assert await catalog.get_match(upcoming_match.id) == upcoming_match


async def test_live_match_round_trips_with_internal_ids_only(
    database: Database,
) -> None:
    catalog = MatchCatalogRepository(database)
    live = _make_match(
        status=MatchStatus.LIVE, scheduled_at=NOW - timedelta(minutes=30)
    )
    await catalog.upsert_matches([live], observed_at=NOW)

    stored = await catalog.get_match(live.id)
    assert stored == live
    assert stored is not None and stored.live_state is None
    assert stored.id.startswith("mat_")
    assert all(player.id.startswith("ply_") for player in stored.players)
    assert stored.tournament.id.startswith("trn_")
    listed = await catalog.list_matches(MatchStatus.LIVE, player_id=live.players[1].id)
    assert listed == [live]


async def test_reupsert_reports_no_new_players(
    database: Database, upcoming_match: Match
) -> None:
    catalog = MatchCatalogRepository(database)
    first = await catalog.upsert_matches([upcoming_match], observed_at=NOW)
    assert first == {upcoming_match.players[0].id, upcoming_match.players[1].id}

    second = await catalog.upsert_matches(
        [upcoming_match], observed_at=NOW + timedelta(minutes=1)
    )
    assert second == set()
    assert await catalog.get_match(upcoming_match.id) is not None


async def test_upsert_never_regresses_finished_match_to_scheduled(
    database: Database,
) -> None:
    catalog = MatchCatalogRepository(database)
    finished = _make_match(
        status=MatchStatus.FINISHED, scheduled_at=NOW - timedelta(hours=2)
    )
    finished = finished.model_copy(update={"winner_player_id": finished.players[0].id})
    await catalog.upsert_matches([finished], observed_at=NOW)

    stale_fixture = finished.model_copy(
        update={
            "status": MatchStatus.SCHEDULED,
            "winner_player_id": None,
            "scheduled_at": NOW + timedelta(days=1),
        }
    )
    inserted = await catalog.upsert_matches(
        [stale_fixture], observed_at=NOW + timedelta(minutes=5)
    )
    assert inserted == set()

    stored = await catalog.get_match(finished.id)
    assert stored is not None
    assert stored.status is MatchStatus.FINISHED
    assert stored.winner_player_id == finished.players[0].id
    assert stored.scheduled_at == finished.scheduled_at


async def test_status_only_moves_forward(
    database: Database, upcoming_match: Match
) -> None:
    catalog = MatchCatalogRepository(database)
    await catalog.upsert_matches([upcoming_match], observed_at=NOW)

    live = upcoming_match.model_copy(update={"status": MatchStatus.LIVE})
    await catalog.upsert_matches([live], observed_at=NOW + timedelta(minutes=10))
    stored = await catalog.get_match(upcoming_match.id)
    assert stored is not None and stored.status is MatchStatus.LIVE

    finished = live.model_copy(
        update={
            "status": MatchStatus.FINISHED,
            "winner_player_id": live.players[1].id,
        }
    )
    await catalog.upsert_matches([finished], observed_at=NOW + timedelta(hours=2))
    stored = await catalog.get_match(upcoming_match.id)
    assert stored is not None and stored.status is MatchStatus.FINISHED
    assert stored.winner_player_id == live.players[1].id


async def test_init_marker_is_idempotent_and_health_never_deletes_catalog(
    database: Database, upcoming_match: Match
) -> None:
    catalog, state = MatchCatalogRepository(database), RuntimeStateRepository(database)
    await catalog.upsert_matches([upcoming_match], observed_at=NOW)
    await state.mark_initialized(
        RuntimeInitRecord(completed_at=NOW, migration_revision="0005")
    )
    await state.mark_initialized(
        RuntimeInitRecord(completed_at=NOW, migration_revision="0005")
    )
    assert await state.is_initialized() is True
    await state.save_health(_health())
    assert await catalog.get_match(upcoming_match.id) is not None


async def test_health_round_trips_and_absent_health_returns_none(
    database: Database,
) -> None:
    state = RuntimeStateRepository(database)
    async with database.session() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM runtime_state WHERE key = 'local_runtime_health'")
            )
    assert await state.load_health() is None

    health = _health()
    await state.save_health(health)
    await state.save_health(health)
    assert await state.load_health() == health

    async with database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT payload FROM runtime_state WHERE key = 'local_runtime_health'"
                )
            )
        ).all()
    assert len(rows) == 1


async def test_runtime_state_stays_within_the_local_runtime_key_pair(
    database: Database,
) -> None:
    state = RuntimeStateRepository(database)
    await state.mark_initialized(
        RuntimeInitRecord(
            completed_at=NOW, migration_revision="0005", player_count=2, match_count=1
        )
    )
    await state.save_health(_health())

    async with database.session() as session:
        rows = (
            await session.execute(text("SELECT key, payload::text FROM runtime_state"))
        ).all()
    assert rows
    assert {key for key, _ in rows} <= {"local_runtime_init", "local_runtime_health"}
    for _, payload in rows:
        lowered = payload.lower()
        for fragment in ("external", "condition", "token", "api_key", "raw"):
            assert fragment not in lowered


async def test_runtime_writes_never_delete_existing_p2_p3_rows(
    database: Database, upcoming_match: Match
) -> None:
    catalog = MatchCatalogRepository(database)
    state = RuntimeStateRepository(database)

    market_id = _internal_id("mkt")
    async with database.session() as session:
        async with session.begin():
            session.add(
                MarketRow(id=market_id, question="Existing P3 market?", status="open")
            )
            session.add(
                RawProviderEventRow(
                    provider="itest",
                    channel="websocket",
                    kind="snapshot",
                    payload={"seq": "existing"},
                    observed_at=NOW,
                )
            )

    async def _table_counts() -> dict[str, int]:
        async with database.session() as session:
            return {
                "players": await session.scalar(
                    select(func.count()).select_from(PlayerRow)
                ),
                "matches": await session.scalar(
                    select(func.count()).select_from(MatchRow)
                ),
                "markets": await session.scalar(
                    select(func.count()).select_from(MarketRow)
                ),
                "raw_provider_events": await session.scalar(
                    select(func.count()).select_from(RawProviderEventRow)
                ),
            }

    before = await _table_counts()

    await catalog.upsert_matches([upcoming_match], observed_at=NOW)
    await state.mark_initialized(
        RuntimeInitRecord(
            completed_at=NOW, migration_revision="0005", player_count=2, match_count=1
        )
    )
    await state.save_health(_health())
    await catalog.upsert_matches(
        [upcoming_match], observed_at=NOW + timedelta(minutes=1)
    )

    after = await _table_counts()
    assert after["players"] == before["players"] + 2
    assert after["matches"] == before["matches"] + 1
    assert after["markets"] == before["markets"]
    assert after["raw_provider_events"] == before["raw_provider_events"]

    async with database.session() as session:
        assert await session.get(MarketRow, market_id) is not None
