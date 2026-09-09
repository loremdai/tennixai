"""Focused P2 repositories (T22 scope).

The cross-table `save_reduction` transaction arrives with the reducer in T26.
Every method here is explicit about the rows it touches; retention deletion
targets only `raw_provider_events.observed_at < before`.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.domain import LiveMatchState
from app.persistence.database import Database
from app.persistence.models import (
    MatchExternalIdRow,
    MatchRow,
    MatchStateSnapshotRow,
    PlayerExternalIdRow,
    PlayerRow,
    RawProviderEventRow,
    TournamentExternalIdRow,
    TournamentRow,
)

_ENTITY_TABLES: dict[str, tuple[type, type, str]] = {
    "match": (MatchRow, MatchExternalIdRow, "mat"),
    "player": (PlayerRow, PlayerExternalIdRow, "ply"),
    "tournament": (TournamentRow, TournamentExternalIdRow, "trn"),
}


def raw_retention_cutoff(now: datetime, *, retention_days: int) -> datetime:
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    return now - timedelta(days=retention_days)


class PostgresIdentityRepository:
    """Durable identity mapping. Internal IDs are stable across processes and
    restarts; concurrent creators converge on one ID via insert-on-conflict
    plus a read retry."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_or_create(self, entity: str, provider: str, external_id: str) -> str:
        try:
            entity_row, external_row, prefix = _ENTITY_TABLES[entity]
        except KeyError:
            raise ValueError(f"unknown entity kind: {entity}") from None
        external_id = str(external_id)

        for attempt in range(3):
            async with self._database.session() as session:
                try:
                    async with session.begin():
                        existing = await session.scalar(
                            select(external_row.internal_id).where(
                                external_row.provider == provider,
                                external_row.external_id == external_id,
                            )
                        )
                        if existing is not None:
                            return existing
                        internal_id = f"{prefix}_{uuid4().hex}"
                        session.add(entity_row(id=internal_id))
                        # Flush the entity row first: without an ORM
                        # relationship the unit of work does not order the
                        # mapping insert after its FK target.
                        await session.flush()
                        session.add(
                            external_row(
                                internal_id=internal_id,
                                provider=provider,
                                external_id=external_id,
                            )
                        )
                    return internal_id
                except IntegrityError:
                    if attempt == 2:
                        raise
                    # A concurrent creator won the race; loop and read its ID.
        raise AssertionError("unreachable")  # pragma: no cover

    async def external_id(
        self, entity: str, provider: str, internal_id: str
    ) -> str | None:
        try:
            _, external_row, _ = _ENTITY_TABLES[entity]
        except KeyError:
            raise ValueError(f"unknown entity kind: {entity}") from None
        async with self._database.session() as session:
            return await session.scalar(
                select(external_row.external_id).where(
                    external_row.provider == provider,
                    external_row.internal_id == internal_id,
                )
            )


class MatchSnapshotRepository:
    """Current canonical live state per match (single row, upserted)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def save_current_state(
        self, *, match_id: str, live_state: LiveMatchState, as_of: datetime
    ) -> None:
        values: dict[str, Any] = {
            "match_id": match_id,
            "state": live_state.model_dump(mode="json"),
            "state_version": live_state.state_version,
            "connection_status": live_state.connection_status.value,
            "as_of": as_of,
            "updated_at": as_of,
        }
        statement = pg_insert(MatchStateSnapshotRow).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=["match_id"],
            set_={
                "state": statement.excluded.state,
                "state_version": statement.excluded.state_version,
                "connection_status": statement.excluded.connection_status,
                "as_of": statement.excluded.as_of,
                "updated_at": statement.excluded.updated_at,
            },
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)

    async def get_current_state(
        self, match_id: str
    ) -> tuple[LiveMatchState, datetime] | None:
        async with self._database.session() as session:
            row = await session.get(MatchStateSnapshotRow, match_id)
        if row is None:
            return None
        return LiveMatchState.model_validate(row.state), row.as_of


class RawProviderEventRepository:
    """Append/read/purge for diagnostic raw payloads (14-day retention)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def append(
        self,
        *,
        provider: str,
        channel: str,
        kind: str,
        payload: dict[str, Any],
        observed_at: datetime,
        match_id: str | None = None,
        external_match_id: str | None = None,
    ) -> int:
        row = RawProviderEventRow(
            match_id=match_id,
            external_match_id=external_match_id,
            provider=provider,
            channel=channel,
            kind=kind,
            payload=payload,
            observed_at=observed_at,
        )
        async with self._database.session() as session:
            async with session.begin():
                session.add(row)
        return row.id

    async def read_for_external_match(
        self, external_match_id: str, *, limit: int = 500
    ) -> list[RawProviderEventRow]:
        async with self._database.session() as session:
            result = await session.execute(
                select(RawProviderEventRow)
                .where(RawProviderEventRow.external_match_id == external_match_id)
                .order_by(RawProviderEventRow.observed_at, RawProviderEventRow.id)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def read_for_match(
        self, match_id: str, *, limit: int = 500
    ) -> list[RawProviderEventRow]:
        async with self._database.session() as session:
            result = await session.execute(
                select(RawProviderEventRow)
                .where(RawProviderEventRow.match_id == match_id)
                .order_by(RawProviderEventRow.observed_at, RawProviderEventRow.id)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def purge_raw_events(self, before: datetime) -> int:
        """Delete raw payloads strictly older than `before`. Never touches
        canonical tables."""
        async with self._database.session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(RawProviderEventRow).where(
                        RawProviderEventRow.observed_at < before
                    )
                )
                return result.rowcount or 0
