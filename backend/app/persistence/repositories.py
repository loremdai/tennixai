"""Focused P2 repositories (T22 scope).

The cross-table `save_reduction` transaction arrives with the reducer in T26.
Every method here is explicit about the rows it touches; retention deletion
targets only `raw_provider_events.observed_at < before`.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

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
    MomentumObservation,
    Player,
    PointEvent,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.persistence.database import Database
from app.persistence.models import (
    MatchExternalIdRow,
    MatchRow,
    MatchStateSnapshotRow,
    MatchStatisticRow,
    MomentumObservationRow,
    PlayerExternalIdRow,
    PlayerRow,
    PointEventRevisionRow,
    PointEventRow,
    RawProviderEventRow,
    TournamentExternalIdRow,
    TournamentRow,
)
from app.realtime.models import LiveReduction

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

    async def load_snapshot(self, match_id: str) -> MatchSnapshot | None:
        """Rebuild the canonical snapshot from PostgreSQL rows."""
        async with self._database.session() as session:
            row = await session.get(MatchStateSnapshotRow, match_id)
            if row is None:
                return None
            match_row = await session.get(MatchRow, match_id)
            if match_row is None:
                return None
            player_rows = {}
            for player_id in (match_row.player1_id, match_row.player2_id):
                if player_id is not None:
                    player_rows[player_id] = await session.get(PlayerRow, player_id)
            tournament_row = (
                await session.get(TournamentRow, match_row.tournament_id)
                if match_row.tournament_id is not None
                else None
            )
            point_rows = (
                (
                    await session.execute(
                        select(PointEventRow)
                        .where(PointEventRow.match_id == match_id)
                        .order_by(PointEventRow.sequence)
                    )
                )
                .scalars()
                .all()
            )
            stat_rows = (
                (
                    await session.execute(
                        select(MatchStatisticRow).where(
                            MatchStatisticRow.match_id == match_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            momentum_rows = (
                (
                    await session.execute(
                        select(MomentumObservationRow)
                        .where(MomentumObservationRow.match_id == match_id)
                        .order_by(
                            MomentumObservationRow.algorithm_version,
                            MomentumObservationRow.point_sequence,
                        )
                    )
                )
                .scalars()
                .all()
            )

        def player_or_placeholder(player_id: str | None) -> Player:
            row = player_rows.get(player_id) if player_id else None
            return Player(
                id=player_id or "ply_unknown",
                name=(row.name if row and row.name else "Unknown player"),
                country_code=row.country_code if row else None,
                ranking=row.ranking if row else None,
            )

        match = Match(
            id=match_row.id,
            status=MatchStatus(match_row.status) if match_row.status else MatchStatus.UNKNOWN,
            players=(
                player_or_placeholder(match_row.player1_id),
                player_or_placeholder(match_row.player2_id),
            ),
            tournament=Tournament(
                id=tournament_row.id if tournament_row else "trn_unknown",
                name=(tournament_row.name if tournament_row and tournament_row.name else "Unknown tournament"),
                tour=tournament_row.tour if tournament_row else None,
                circuit=CircuitTier(tournament_row.circuit) if tournament_row else CircuitTier.OTHER,
                gender=Gender(tournament_row.gender) if tournament_row else Gender.UNKNOWN,
                discipline=Discipline(tournament_row.discipline) if tournament_row else Discipline.UNKNOWN,
            ),
            scheduled_at=match_row.scheduled_at,
            round=match_row.round,
            surface=match_row.surface,
            indoor=match_row.indoor,
            format=match_row.format,
            live_state=LiveMatchState.model_validate(row.state),
            winner_player_id=match_row.winner_player_id,
            freshness=DataFreshness(provider="postgres", observed_at=row.as_of),
        )
        points = tuple(
            PointEvent(
                id=point.id,
                match_id=point.match_id,
                sequence=point.sequence,
                set_number=point.set_number,
                game_number=point.game_number,
                point_number=point.point_number,
                server_player_id=point.server_player_id,
                winner_player_id=point.winner_player_id,
                score_before=(
                    MatchScore.model_validate(point.score_before)
                    if point.score_before is not None
                    else None
                ),
                score_after=MatchScore.model_validate(point.score_after),
                is_break_point=point.is_break_point,
                is_set_point=point.is_set_point,
                is_match_point=point.is_match_point,
                observed_at=point.observed_at,
                provider=point.provider,
                source_fingerprint=point.source_fingerprint,
                revision=point.revision,
                quality=(
                    DataQuality.model_validate(point.quality)
                    if point.quality is not None
                    else None
                ),
            )
            for point in point_rows
        )
        statistics = tuple(
            MatchStatistic(
                match_id=stat.match_id,
                name=StatisticName(stat.name),
                period=stat.period,
                player1_value=stat.player1_value,
                player2_value=stat.player2_value,
                unit=stat.unit,
                provenance=StatisticProvenance(stat.provenance),
                availability=CapabilityStatus(stat.availability),
                as_of=stat.as_of,
            )
            for stat in stat_rows
        )
        momentum = tuple(
            MomentumObservation(
                match_id=observation.match_id,
                point_sequence=observation.point_sequence,
                state_version=observation.state_version,
                algorithm_version=observation.algorithm_version,
                value=observation.value,
                leader_player_id=observation.leader_player_id,
                is_provisional=observation.is_provisional,
                as_of=observation.as_of,
                input_summary=observation.input_summary,
            )
            for observation in momentum_rows
        )
        quality = tuple(DataQuality.model_validate(item) for item in (row.quality or []))
        return MatchSnapshot(
            match=match,
            points=points,
            statistics=statistics,
            momentum=momentum,
            quality=quality,
            state_version=row.state_version,
            as_of=row.as_of,
        )

    async def save_reduction(
        self,
        reduction: LiveReduction,
        *,
        before_commit: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        """Persist snapshot, points, revisions, statistics and quality in one
        transaction. Returns only after commit; a failed transaction leaves
        the previous version fully readable."""
        snapshot = reduction.snapshot
        live_state = snapshot.match.live_state or LiveMatchState()
        quality_payload = [item.model_dump(mode="json") for item in snapshot.quality]

        async with self._database.session() as session:
            async with session.begin():
                match = snapshot.match
                for player in match.players:
                    player_statement = pg_insert(PlayerRow).values(
                        id=player.id,
                        name=player.name,
                        country_code=player.country_code,
                        ranking=player.ranking,
                    )
                    await session.execute(
                        player_statement.on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "name": player_statement.excluded.name,
                                "country_code": player_statement.excluded.country_code,
                                "ranking": player_statement.excluded.ranking,
                                "updated_at": func.now(),
                            },
                        )
                    )
                tournament = match.tournament
                tournament_statement = pg_insert(TournamentRow).values(
                    id=tournament.id,
                    name=tournament.name,
                    tour=tournament.tour,
                    circuit=tournament.circuit.value,
                    gender=tournament.gender.value,
                    discipline=tournament.discipline.value,
                )
                await session.execute(
                    tournament_statement.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "name": tournament_statement.excluded.name,
                            "tour": tournament_statement.excluded.tour,
                            "circuit": tournament_statement.excluded.circuit,
                            "gender": tournament_statement.excluded.gender,
                            "discipline": tournament_statement.excluded.discipline,
                            "updated_at": func.now(),
                        },
                    )
                )
                match_statement = pg_insert(MatchRow).values(
                    id=match.id,
                    status=match.status.value,
                    player1_id=match.players[0].id,
                    player2_id=match.players[1].id,
                    tournament_id=match.tournament.id,
                    scheduled_at=match.scheduled_at,
                    round=match.round,
                    surface=match.surface,
                    indoor=match.indoor,
                    format=match.format,
                    winner_player_id=match.winner_player_id,
                )
                await session.execute(
                    match_statement.on_conflict_do_update(
                        index_elements=["id"],
                        set_={
                            "status": match_statement.excluded.status,
                            "player1_id": match_statement.excluded.player1_id,
                            "player2_id": match_statement.excluded.player2_id,
                            "tournament_id": match_statement.excluded.tournament_id,
                            "scheduled_at": match_statement.excluded.scheduled_at,
                            "round": match_statement.excluded.round,
                            "surface": match_statement.excluded.surface,
                            "indoor": match_statement.excluded.indoor,
                            "format": match_statement.excluded.format,
                            "winner_player_id": match_statement.excluded.winner_player_id,
                            "updated_at": func.now(),
                        },
                    )
                )

                statement = pg_insert(MatchStateSnapshotRow).values(
                    match_id=reduction.match_id,
                    state=live_state.model_dump(mode="json"),
                    state_version=snapshot.state_version,
                    connection_status=live_state.connection_status.value,
                    as_of=snapshot.as_of,
                    quality=quality_payload,
                    updated_at=snapshot.as_of,
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=["match_id"],
                        set_={
                            "state": statement.excluded.state,
                            "state_version": statement.excluded.state_version,
                            "connection_status": statement.excluded.connection_status,
                            "as_of": statement.excluded.as_of,
                            "quality": statement.excluded.quality,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )

                for point in snapshot.points:
                    values = {
                        "id": point.id,
                        "match_id": point.match_id,
                        "sequence": point.sequence,
                        "set_number": point.set_number,
                        "game_number": point.game_number,
                        "point_number": point.point_number,
                        "server_player_id": point.server_player_id,
                        "winner_player_id": point.winner_player_id,
                        "score_before": (
                            point.score_before.model_dump(mode="json")
                            if point.score_before is not None
                            else None
                        ),
                        "score_after": point.score_after.model_dump(mode="json"),
                        "is_break_point": point.is_break_point,
                        "is_set_point": point.is_set_point,
                        "is_match_point": point.is_match_point,
                        "observed_at": point.observed_at,
                        "provider": point.provider,
                        "source_fingerprint": point.source_fingerprint,
                        "revision": point.revision,
                        "quality": (
                            point.quality.model_dump(mode="json")
                            if point.quality is not None
                            else None
                        ),
                    }
                    point_statement = pg_insert(PointEventRow).values(**values)
                    await session.execute(
                        point_statement.on_conflict_do_update(
                            # `sequence` is the current canonical row identity.
                            # A provider correction can rebuild a tail and move
                            # a point's supplier-derived id, so upserting by id
                            # can violate the unique (match_id, sequence) key.
                            index_elements=["match_id", "sequence"],
                            set_={
                                key: point_statement.excluded[key]
                                for key in (
                                    "set_number",
                                    "game_number",
                                    "point_number",
                                    "server_player_id",
                                    "winner_player_id",
                                    "score_before",
                                    "score_after",
                                    "is_break_point",
                                    "is_set_point",
                                    "is_match_point",
                                    "observed_at",
                                    "source_fingerprint",
                                    "revision",
                                    "quality",
                                )
                            },
                        )
                    )

                for revision in reduction.point_revisions:
                    revision_statement = pg_insert(PointEventRevisionRow).values(
                        point_event_id=revision.point_id,
                        revision=revision.revision,
                        before_state=revision.before.model_dump(mode="json"),
                        after_state=revision.after.model_dump(mode="json"),
                        revised_at=revision.revised_at,
                        reason=revision.reason,
                    )
                    await session.execute(
                        revision_statement.on_conflict_do_nothing(
                            index_elements=["point_event_id", "revision"]
                        )
                    )

                for statistic in reduction.statistics:
                    statistic_statement = pg_insert(MatchStatisticRow).values(
                        match_id=statistic.match_id,
                        name=statistic.name.value,
                        period=statistic.period,
                        player1_value=statistic.player1_value,
                        player2_value=statistic.player2_value,
                        unit=statistic.unit,
                        provenance=statistic.provenance.value,
                        availability=statistic.availability.value,
                        as_of=statistic.as_of,
                    )
                    await session.execute(
                        statistic_statement.on_conflict_do_update(
                            index_elements=["match_id", "name", "period"],
                            set_={
                                "player1_value": statistic_statement.excluded.player1_value,
                                "player2_value": statistic_statement.excluded.player2_value,
                                "unit": statistic_statement.excluded.unit,
                                "provenance": statistic_statement.excluded.provenance,
                                "availability": statistic_statement.excluded.availability,
                                "as_of": statistic_statement.excluded.as_of,
                            },
                        )
                    )

                from app.momentum.engine import ALGORITHM_VERSION

                momentum_sequences = {
                    observation.point_sequence for observation in snapshot.momentum
                }
                momentum_delete = delete(MomentumObservationRow).where(
                    MomentumObservationRow.match_id == reduction.match_id,
                    MomentumObservationRow.algorithm_version == ALGORITHM_VERSION,
                )
                if momentum_sequences:
                    momentum_delete = momentum_delete.where(
                        MomentumObservationRow.point_sequence.not_in(momentum_sequences)
                    )
                await session.execute(momentum_delete)
                for observation in snapshot.momentum:
                    observation_statement = pg_insert(MomentumObservationRow).values(
                        match_id=observation.match_id,
                        point_sequence=observation.point_sequence,
                        state_version=observation.state_version,
                        algorithm_version=observation.algorithm_version,
                        value=observation.value,
                        leader_player_id=observation.leader_player_id,
                        is_provisional=observation.is_provisional,
                        as_of=observation.as_of,
                        input_summary=observation.input_summary,
                    )
                    await session.execute(
                        observation_statement.on_conflict_do_update(
                            index_elements=[
                                "match_id",
                                "algorithm_version",
                                "point_sequence",
                            ],
                            set_={
                                "state_version": observation_statement.excluded.state_version,
                                "value": observation_statement.excluded.value,
                                "leader_player_id": observation_statement.excluded.leader_player_id,
                                "is_provisional": observation_statement.excluded.is_provisional,
                                "as_of": observation_statement.excluded.as_of,
                                "input_summary": observation_statement.excluded.input_summary,
                            },
                        )
                    )
                if before_commit is not None:
                    await before_commit(session)


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
