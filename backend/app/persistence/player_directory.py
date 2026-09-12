"""PostgreSQL player directory repository (P2.6 T45).

Shares semantics with `MemoryPlayerDirectoryRepository`: idempotent alias
writes, ambiguity-preserving alias lookups, latest-snapshot ranking reads and
all-or-nothing localized-name batches. Vendor payloads never land here.
"""

from datetime import date

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import Gender, Player
from app.errors import AppError
from app.persistence.database import Database
from app.persistence.models import PlayerAliasRow, PlayerRankingRow, PlayerRow
from app.players.models import (
    AliasMatch,
    DirectoryPlayer,
    LocalizedNameUpdate,
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
    RankingEntry,
    RankingMovement,
    Tour,
)
from app.players.repository import ALIAS_KIND_PRIORITY


def _directory_player(row: PlayerRow) -> DirectoryPlayer:
    return DirectoryPlayer(
        player=Player(
            id=row.id,
            name=row.name or "Unknown player",
            localized_name=row.localized_name,
            country_code=row.country_code,
            ranking=row.ranking,
        ),
        gender=Gender(row.gender) if row.gender in Gender.__members__.values() else Gender.UNKNOWN,
        birth_date=row.birth_date,
        image_url=row.image_url,
    )


def _ranking_entry(row: PlayerRankingRow, player: Player) -> RankingEntry:
    return RankingEntry(
        player=player,
        tour=Tour(row.tour),
        rank=row.rank,
        points=row.points,
        movement=RankingMovement(row.movement),
        ranking_date=row.ranking_date,
        fetched_at=row.fetched_at,
    )


class PostgresPlayerDirectoryRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save_ranking_snapshot(self, entries: tuple[RankingEntry, ...]) -> None:
        async with self._database.session() as session:
            async with session.begin():
                for entry in entries:
                    values = {
                        "id": entry.player.id,
                        "name": entry.player.name,
                        "country_code": entry.player.country_code,
                        "ranking": entry.rank,
                        "last_seen_at": entry.fetched_at,
                        "updated_at": entry.fetched_at,
                    }
                    statement = pg_insert(PlayerRow).values(**values)
                    await session.execute(
                        statement.on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "name": statement.excluded.name,
                                "country_code": statement.excluded.country_code,
                                "ranking": statement.excluded.ranking,
                                "last_seen_at": statement.excluded.last_seen_at,
                                "updated_at": statement.excluded.updated_at,
                            },
                        )
                    )
                tours_dates = {
                    (entry.tour.value, entry.ranking_date) for entry in entries
                }
                for tour_value, ranking_date in tours_dates:
                    await session.execute(
                        delete(PlayerRankingRow).where(
                            PlayerRankingRow.tour == tour_value,
                            PlayerRankingRow.ranking_date == ranking_date,
                        )
                    )
                for entry in entries:
                    session.add(
                        PlayerRankingRow(
                            player_id=entry.player.id,
                            tour=entry.tour.value,
                            ranking_date=entry.ranking_date,
                            rank=entry.rank,
                            points=entry.points,
                            movement=entry.movement.value,
                            fetched_at=entry.fetched_at,
                        )
                    )

    async def upsert_aliases(self, aliases: tuple[PlayerAlias, ...]) -> int:
        if not aliases:
            return 0
        inserted = 0
        async with self._database.session() as session:
            async with session.begin():
                for alias in aliases:
                    statement = pg_insert(PlayerAliasRow).values(
                        player_id=alias.player_id,
                        locale=alias.locale,
                        alias=alias.alias,
                        normalized_alias=alias.normalized_alias,
                        kind=alias.kind.value,
                        source=alias.source.value,
                        source_ref=alias.source_ref,
                        model=alias.model,
                        prompt_version=alias.prompt_version,
                    )
                    result = await session.execute(statement.on_conflict_do_nothing())
                    inserted += result.rowcount or 0
        return inserted

    async def save_localized_names(self, updates: tuple[LocalizedNameUpdate, ...]) -> int:
        if not updates:
            return 0
        async with self._database.session() as session:
            async with session.begin():
                player_ids = [update.player_id for update in updates]
                existing = (
                    await session.execute(
                        select(PlayerRow.id).where(PlayerRow.id.in_(player_ids))
                    )
                ).scalars().all()
                missing = set(player_ids) - set(existing)
                if missing:
                    raise AppError(
                        "invalid_request",
                        "Localized name batch references unknown players",
                        422,
                        {"player_ids": sorted(missing)},
                    )
                for change in updates:
                    await session.execute(
                        update(PlayerRow)
                        .where(PlayerRow.id == change.player_id)
                        .values(
                            localized_name=change.localized_name,
                            updated_at=func.now(),
                        )
                    )
                for change in updates:
                    for alias in change.aliases:
                        statement = pg_insert(PlayerAliasRow).values(
                            player_id=alias.player_id,
                            locale=alias.locale,
                            alias=alias.alias,
                            normalized_alias=alias.normalized_alias,
                            kind=alias.kind.value,
                            source=alias.source.value,
                            source_ref=alias.source_ref,
                            model=alias.model,
                            prompt_version=alias.prompt_version,
                        )
                        await session.execute(statement.on_conflict_do_nothing())
        return len(updates)

    async def get_player(self, player_id: str) -> DirectoryPlayer | None:
        async with self._database.session() as session:
            row = await session.get(PlayerRow, player_id)
        return _directory_player(row) if row else None

    async def get_rankings(
        self,
        tour: Tour,
        *,
        page: int,
        page_size: int,
        country_code: str | None,
    ) -> tuple[tuple[RankingEntry, ...], int]:
        async with self._database.session() as session:
            latest = (
                await session.execute(
                    select(func.max(PlayerRankingRow.ranking_date)).where(
                        PlayerRankingRow.tour == tour.value
                    )
                )
            ).scalar()
            if latest is None:
                return (), 0
            conditions = [
                PlayerRankingRow.tour == tour.value,
                PlayerRankingRow.ranking_date == latest,
            ]
            if country_code is not None:
                conditions.append(PlayerRow.country_code == country_code)
            total = (
                await session.execute(
                    select(func.count())
                    .select_from(PlayerRankingRow)
                    .join(PlayerRow, PlayerRow.id == PlayerRankingRow.player_id)
                    .where(*conditions)
                )
            ).scalar() or 0
            rows = (
                await session.execute(
                    select(PlayerRankingRow, PlayerRow)
                    .join(PlayerRow, PlayerRow.id == PlayerRankingRow.player_id)
                    .where(*conditions)
                    .order_by(PlayerRankingRow.rank, PlayerRankingRow.player_id)
                    .limit(page_size)
                    .offset((max(1, page) - 1) * page_size)
                )
            ).all()
        entries = tuple(
            _ranking_entry(
                ranking_row,
                Player(
                    id=player_row.id,
                    name=player_row.name or "Unknown player",
                    localized_name=player_row.localized_name,
                    country_code=player_row.country_code,
                    ranking=player_row.ranking,
                ),
            )
            for ranking_row, player_row in rows
        )
        return entries, int(total)

    async def find_aliases(self, normalized_query: str, *, limit: int) -> tuple[AliasMatch, ...]:
        priority_case = _kind_priority_expression()
        async with self._database.session() as session:
            rows = (
                await session.execute(
                    select(PlayerAliasRow, PlayerRow)
                    .join(PlayerRow, PlayerRow.id == PlayerAliasRow.player_id)
                    .where(
                        PlayerAliasRow.normalized_alias == normalized_query,
                        PlayerAliasRow.is_active.is_(True),
                    )
                    .order_by(
                        priority_case,
                        PlayerRow.ranking.is_(None),
                        PlayerRow.ranking.asc(),
                        PlayerRow.id,
                    )
                    .limit(limit)
                )
            ).all()
        return tuple(
            AliasMatch(
                player=_directory_player(player_row),
                alias=PlayerAlias(
                    player_id=alias_row.player_id,
                    locale=alias_row.locale,
                    alias=alias_row.alias,
                    normalized_alias=alias_row.normalized_alias,
                    kind=PlayerAliasKind(alias_row.kind),
                    source=PlayerAliasSource(alias_row.source),
                    source_ref=alias_row.source_ref,
                    model=alias_row.model,
                    prompt_version=alias_row.prompt_version,
                ),
                current_rank=player_row.ranking,
            )
            for alias_row, player_row in rows
        )

    async def list_players_missing_localized_name(
        self, *, limit: int
    ) -> tuple[DirectoryPlayer, ...]:
        async with self._database.session() as session:
            rows = (
                await session.execute(
                    select(PlayerRow)
                    .where(PlayerRow.localized_name.is_(None))
                    .order_by(PlayerRow.id)
                    .limit(limit)
                )
            ).scalars().all()
        return tuple(_directory_player(row) for row in rows)

    async def list_players_for_alias_sync(
        self, *, limit: int, after_id: str | None = None
    ) -> tuple[DirectoryPlayer, ...]:
        conditions = [PlayerRow.name.is_not(None), PlayerRow.name != ""]
        if after_id is not None:
            conditions.append(PlayerRow.id > after_id)
        async with self._database.session() as session:
            rows = (
                await session.execute(
                    select(PlayerRow).where(*conditions).order_by(PlayerRow.id).limit(limit)
                )
            ).scalars().all()
        return tuple(_directory_player(row) for row in rows)

    async def prune_ranking_snapshots(self, *, keep_per_tour: int = 8) -> int:
        removed = 0
        async with self._database.session() as session:
            async with session.begin():
                for tour in Tour:
                    kept_dates = (
                        await session.execute(
                            select(PlayerRankingRow.ranking_date)
                            .where(PlayerRankingRow.tour == tour.value)
                            .distinct()
                            .order_by(PlayerRankingRow.ranking_date.desc())
                            .limit(keep_per_tour)
                        )
                    ).scalars().all()
                    if not kept_dates:
                        continue
                    result = await session.execute(
                        delete(PlayerRankingRow).where(
                            PlayerRankingRow.tour == tour.value,
                            PlayerRankingRow.ranking_date.not_in(list(kept_dates)),
                        )
                    )
                    removed += result.rowcount or 0
        return removed

    async def directory_counts(self) -> dict[str, int]:
        async with self._database.session() as session:
            players = (
                await session.execute(select(func.count()).select_from(PlayerRow))
            ).scalar() or 0
            localized = (
                await session.execute(
                    select(func.count())
                    .select_from(PlayerRow)
                    .where(PlayerRow.localized_name.is_not(None))
                )
            ).scalar() or 0
            aliases = (
                await session.execute(select(func.count()).select_from(PlayerAliasRow))
            ).scalar() or 0
            ranked: dict[str, int] = {}
            for tour in Tour:
                latest = (
                    await session.execute(
                        select(func.max(PlayerRankingRow.ranking_date)).where(
                            PlayerRankingRow.tour == tour.value
                        )
                    )
                ).scalar()
                if latest is None:
                    ranked[tour.value] = 0
                    continue
                ranked[tour.value] = (
                    await session.execute(
                        select(func.count())
                        .select_from(PlayerRankingRow)
                        .where(
                            PlayerRankingRow.tour == tour.value,
                            PlayerRankingRow.ranking_date == latest,
                        )
                    )
                ).scalar() or 0
        return {
            "players": int(players),
            "localized": int(localized),
            "aliases": int(aliases),
            "ranked_atp": int(ranked[Tour.ATP.value]),
            "ranked_wta": int(ranked[Tour.WTA.value]),
        }


def _kind_priority_expression():
    """ORDER BY term mirroring ALIAS_KIND_PRIORITY in the memory repository."""
    whens = [
        (PlayerAliasRow.kind == kind, priority)
        for kind, priority in sorted(ALIAS_KIND_PRIORITY.items(), key=lambda item: item[1])
    ]
    return case(*whens, else_=len(ALIAS_KIND_PRIORITY))
