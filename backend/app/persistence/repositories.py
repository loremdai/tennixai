"""Canonical PostgreSQL repositories across P2, P3 and P4.1.

Holds the P2 identity/snapshot/raw-event stores (including the cross-table
`save_reduction` transaction added with the reducer in T26), the P3 canonical
match catalog, and the P4.1 runtime-state repository. Every method here is
explicit about the rows it touches; retention deletion targets only
`raw_provider_events.observed_at < before`.
"""

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, case, delete, func, not_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.persistence.player_directory import _latest_ranking_rows
from app.persistence.models import (
    MatchExternalIdRow,
    MatchRow,
    MatchStateSnapshotRow,
    MatchStatisticRow,
    MomentumObservationRow,
    PlayerExternalIdRow,
    PlayerRankingRow,
    PlayerRow,
    PointEventRevisionRow,
    PointEventRow,
    RawProviderEventRow,
    RuntimeStateRow,
    TournamentExternalIdRow,
    TournamentRow,
)
from app.realtime.models import LiveReduction
from app.runtime.models import RuntimeHealth, RuntimeInitRecord

_ENTITY_TABLES: dict[str, tuple[type, type, str]] = {
    "match": (MatchRow, MatchExternalIdRow, "mat"),
    "player": (PlayerRow, PlayerExternalIdRow, "ply"),
    "tournament": (TournamentRow, TournamentExternalIdRow, "trn"),
}


def raw_retention_cutoff(now: datetime, *, retention_days: int) -> datetime:
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    return now - timedelta(days=retention_days)


def _is_initial_abbreviation(value):
    return value.op("~*")(r"(^|[[:space:]])[[:alpha:]]\.")


def _player_conflict_updates(statement, *, observed_at: datetime | None = None) -> dict:
    incoming_name = statement.excluded.name
    name = case(
        (or_(PlayerRow.name.is_(None), PlayerRow.name == ""), incoming_name),
        (
            and_(
                _is_initial_abbreviation(PlayerRow.name),
                not_(_is_initial_abbreviation(incoming_name)),
            ),
            incoming_name,
        ),
        else_=PlayerRow.name,
    )
    values = {
        "name": name,
        "localized_name": func.coalesce(
            statement.excluded.localized_name, PlayerRow.localized_name
        ),
        "image_url": func.coalesce(statement.excluded.image_url, PlayerRow.image_url),
        "country_code": func.coalesce(
            PlayerRow.country_code, statement.excluded.country_code
        ),
        # Current ranking is owned only by the standings snapshot.
        "ranking": PlayerRow.ranking,
        "updated_at": observed_at if observed_at is not None else func.now(),
    }
    if observed_at is not None:
        values["last_seen_at"] = observed_at
    return values


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
            current_rankings = await _latest_ranking_rows(
                session, {player_id for player_id in player_rows if player_id}
            )
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
                localized_name=row.localized_name if row else None,
                country_code=row.country_code if row else None,
                image_url=row.image_url if row else None,
                ranking=(
                    current_rankings[player_id].rank
                    if player_id in current_rankings
                    else None
                ),
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
            freshness=(
                DataFreshness.model_validate(row.freshness)
                if row.freshness is not None
                else DataFreshness(provider="unknown", observed_at=row.as_of)
            ),
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
                        localized_name=player.localized_name,
                        country_code=player.country_code,
                        image_url=player.image_url,
                        ranking=None,
                    )
                    await session.execute(
                        player_statement.on_conflict_do_update(
                            index_elements=["id"],
                            set_=_player_conflict_updates(player_statement),
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
                    freshness=snapshot.match.freshness.model_dump(
                        mode="json", exclude={"is_stale", "age_seconds"}
                    ),
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
                            "freshness": statement.excluded.freshness,
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


# ---------------------------------------------------------------------------
# P4.1 local runtime catalog and state (T74). The catalog reuses the P2
# players/tournaments/matches rows and stores canonical facts with internal
# IDs only; `runtime_state` holds the init marker and health summary payloads
# and never provider identifiers or raw provider JSON.
# ---------------------------------------------------------------------------

CATALOG_FRESHNESS_PROVIDER = "catalog"

RUNTIME_INIT_STATE_KEY = "local_runtime_init"
RUNTIME_HEALTH_STATE_KEY = "local_runtime_health"

_MATCH_STATUS_RANK: dict[MatchStatus, int] = {
    MatchStatus.SCHEDULED: 0,
    MatchStatus.POSTPONED: 0,
    MatchStatus.UNKNOWN: 0,
    MatchStatus.LIVE: 1,
    MatchStatus.FINISHED: 2,
    MatchStatus.CANCELLED: 2,
}


def is_match_status_regression(
    existing: MatchStatus | None, incoming: MatchStatus
) -> bool:
    """True when `incoming` would move a stored catalog status backwards.

    Statuses only move forward (scheduled/postponed/unknown → live →
    finished/cancelled), so an older fixture row can never reset a finished
    match to scheduled.
    """
    if existing is None:
        return False
    return _MATCH_STATUS_RANK[existing] > _MATCH_STATUS_RANK[incoming]


class UnknownRuntimeStateKeyError(Exception):
    """Raised when a `runtime_state` key outside the local runtime pair
    (`local_runtime_init`, `local_runtime_health`) is requested."""


def require_runtime_state_key(key: str) -> str:
    if key not in (RUNTIME_INIT_STATE_KEY, RUNTIME_HEALTH_STATE_KEY):
        raise UnknownRuntimeStateKeyError(key)
    return key


class MatchCatalogRepository:
    """Canonical match catalog on top of the existing P2 tables.

    Reads return canonical `Match` objects with internal IDs only. Live
    snapshots stay in `match_state_snapshots`; the catalog never copies
    them, never mirrors provider JSON and never deletes rows.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert_matches(
        self, matches: Sequence[Match], *, observed_at: datetime
    ) -> set[str]:
        """Upsert canonical matches; return the internal IDs of players that
        were newly inserted into the players table by this call."""
        player_ids = {player.id for match in matches for player in match.players}
        async with self._database.session() as session:
            async with session.begin():
                existing_player_ids: set[str] = set()
                if player_ids:
                    rows = await session.execute(
                        select(PlayerRow.id).where(PlayerRow.id.in_(player_ids))
                    )
                    existing_player_ids = set(rows.scalars().all())
                for match in matches:
                    await self._upsert_match(session, match, observed_at=observed_at)
                return player_ids - existing_player_ids

    async def list_matches(
        self, status: MatchStatus, *, player_id: str | None = None
    ) -> list[Match]:
        query = select(MatchRow).where(MatchRow.status == status.value)
        if player_id is not None:
            query = query.where(
                or_(
                    MatchRow.player1_id == player_id,
                    MatchRow.player2_id == player_id,
                )
            )
        query = query.order_by(MatchRow.scheduled_at.asc().nulls_last(), MatchRow.id)
        async with self._database.session() as session:
            rows = list((await session.execute(query)).scalars().all())
            return await self._load_matches(session, rows)

    async def get_match(self, match_id: str) -> Match | None:
        async with self._database.session() as session:
            row = await session.get(MatchRow, match_id)
            if row is None:
                return None
            return (await self._load_matches(session, [row]))[0]

    async def _upsert_match(
        self, session: AsyncSession, match: Match, *, observed_at: datetime
    ) -> None:
        for player in match.players:
            player_statement = pg_insert(PlayerRow).values(
                id=player.id,
                name=player.name,
                localized_name=player.localized_name,
                country_code=player.country_code,
                image_url=player.image_url,
                ranking=None,
                last_seen_at=observed_at,
            )
            await session.execute(
                player_statement.on_conflict_do_update(
                    index_elements=["id"],
                    set_=_player_conflict_updates(
                        player_statement, observed_at=observed_at
                    ),
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
                    "updated_at": observed_at,
                },
            )
        )
        stored_status = await session.scalar(
            select(MatchRow.status).where(MatchRow.id == match.id)
        )
        if is_match_status_regression(
            MatchStatus(stored_status) if stored_status else None, match.status
        ):
            # An older fixture arrived after the match progressed; keep the
            # stored canonical facts instead of regressing them.
            return
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
            updated_at=observed_at,
        )
        # Single-writer assumption: only the runtime daemon upserts catalog
        # rows. A partial incoming fixture (provider omitted optional fields)
        # must never clobber already-populated canonical facts, so nullable
        # fields keep the stored value when the incoming one is NULL; status
        # is separately protected by the regression guard above.
        await session.execute(
            match_statement.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": match_statement.excluded.status,
                    "player1_id": match_statement.excluded.player1_id,
                    "player2_id": match_statement.excluded.player2_id,
                    "tournament_id": match_statement.excluded.tournament_id,
                    "scheduled_at": func.coalesce(
                        match_statement.excluded.scheduled_at, MatchRow.scheduled_at
                    ),
                    "round": func.coalesce(
                        match_statement.excluded.round, MatchRow.round
                    ),
                    "surface": func.coalesce(
                        match_statement.excluded.surface, MatchRow.surface
                    ),
                    "indoor": func.coalesce(
                        match_statement.excluded.indoor, MatchRow.indoor
                    ),
                    "format": func.coalesce(
                        match_statement.excluded.format, MatchRow.format
                    ),
                    "winner_player_id": func.coalesce(
                        match_statement.excluded.winner_player_id,
                        MatchRow.winner_player_id,
                    ),
                    "updated_at": match_statement.excluded.updated_at,
                },
            )
        )

    async def _load_matches(
        self, session: AsyncSession, rows: Sequence[MatchRow]
    ) -> list[Match]:
        player_ids = {
            player_id
            for row in rows
            for player_id in (row.player1_id, row.player2_id)
            if player_id is not None
        }
        tournament_ids = {
            row.tournament_id for row in rows if row.tournament_id is not None
        }
        player_rows: dict[str, PlayerRow] = {}
        current_rankings = {}
        if player_ids:
            player_rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(PlayerRow).where(PlayerRow.id.in_(player_ids))
                    )
                ).scalars()
            }
            current_rankings = await _latest_ranking_rows(session, player_ids)
        tournament_rows: dict[str, TournamentRow] = {}
        if tournament_ids:
            tournament_rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(TournamentRow).where(
                            TournamentRow.id.in_(tournament_ids)
                        )
                    )
                ).scalars()
            }
        return [
            self._to_match(row, player_rows, tournament_rows, current_rankings)
            for row in rows
        ]

    @staticmethod
    def _to_match(
        row: MatchRow,
        player_rows: dict[str, PlayerRow],
        tournament_rows: dict[str, TournamentRow],
        current_rankings: dict[str, PlayerRankingRow],
    ) -> Match:
        def player_or_placeholder(player_id: str | None) -> Player:
            player_row = player_rows.get(player_id) if player_id else None
            return Player(
                id=player_id or "ply_unknown",
                name=(
                    player_row.name
                    if player_row and player_row.name
                    else "Unknown player"
                ),
                localized_name=player_row.localized_name if player_row else None,
                country_code=player_row.country_code if player_row else None,
                image_url=player_row.image_url if player_row else None,
                ranking=(
                    current_rankings[player_id].rank
                    if player_id in current_rankings
                    else None
                ),
            )

        tournament_row = (
            tournament_rows.get(row.tournament_id) if row.tournament_id else None
        )
        return Match(
            id=row.id,
            status=MatchStatus(row.status) if row.status else MatchStatus.UNKNOWN,
            players=(
                player_or_placeholder(row.player1_id),
                player_or_placeholder(row.player2_id),
            ),
            tournament=Tournament(
                id=tournament_row.id if tournament_row else "trn_unknown",
                name=(
                    tournament_row.name
                    if tournament_row and tournament_row.name
                    else "Unknown tournament"
                ),
                tour=tournament_row.tour if tournament_row else None,
                circuit=(
                    CircuitTier(tournament_row.circuit)
                    if tournament_row
                    else CircuitTier.OTHER
                ),
                gender=(
                    Gender(tournament_row.gender) if tournament_row else Gender.UNKNOWN
                ),
                discipline=(
                    Discipline(tournament_row.discipline)
                    if tournament_row
                    else Discipline.UNKNOWN
                ),
            ),
            scheduled_at=row.scheduled_at,
            round=row.round,
            surface=row.surface,
            indoor=row.indoor,
            format=row.format,
            live_state=None,
            winner_player_id=row.winner_player_id,
            freshness=DataFreshness(
                provider=CATALOG_FRESHNESS_PROVIDER, observed_at=row.updated_at
            ),
        )


class RuntimeStateRepository:
    """Init marker and health summary in `runtime_state`.

    Only the two local runtime keys are accepted; payloads are canonical
    model dumps and never contain provider identifiers, raw events or
    secrets. Upserts never touch catalog tables.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def is_initialized(self) -> bool:
        async with self._database.session() as session:
            key = await session.scalar(
                select(RuntimeStateRow.key).where(
                    RuntimeStateRow.key == RUNTIME_INIT_STATE_KEY
                )
            )
        return key is not None

    async def mark_initialized(self, record: RuntimeInitRecord) -> None:
        await self._upsert_payload(
            RUNTIME_INIT_STATE_KEY,
            record.model_dump(mode="json"),
            updated_at=record.completed_at,
        )

    async def save_health(self, health: RuntimeHealth) -> None:
        await self._upsert_payload(
            RUNTIME_HEALTH_STATE_KEY,
            health.model_dump(mode="json"),
            updated_at=health.generated_at,
        )

    async def load_health(self) -> RuntimeHealth | None:
        async with self._database.session() as session:
            row = await session.get(
                RuntimeStateRow, require_runtime_state_key(RUNTIME_HEALTH_STATE_KEY)
            )
        if row is None:
            return None
        return RuntimeHealth.model_validate(row.payload)

    async def _upsert_payload(
        self, key: str, payload: dict[str, Any], *, updated_at: datetime
    ) -> None:
        require_runtime_state_key(key)
        statement = pg_insert(RuntimeStateRow).values(
            key=key, payload=payload, updated_at=updated_at
        )
        statement = statement.on_conflict_do_update(
            index_elements=["key"],
            set_={
                "payload": statement.excluded.payload,
                "updated_at": statement.excluded.updated_at,
            },
        )
        async with self._database.session() as session:
            async with session.begin():
                await session.execute(statement)
