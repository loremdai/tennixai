"""Canonical live reducer (spec §10).

Turns a full supplier snapshot (canonical candidate) into a versioned
reduction against the previous state: identical snapshots are ignored, new
points are appended, changed old points become revisions, and dropped or
reordered tails are rebuilt from the first difference. `state_version`
advances only on semantic change.
"""

from app.domain import LiveMatchState, Match, MatchSnapshot, MomentumObservation, PointEvent
from app.momentum.engine import RecentControlEngine
from app.realtime.models import (
    CHANGE_ORDER,
    LiveReduction,
    PointRevision,
    ReductionChange,
)


def _point_identity(point: PointEvent) -> tuple[int, int, int]:
    return (point.set_number, point.game_number, point.point_number)


def _point_fingerprint(point: PointEvent) -> tuple:
    return (
        point.source_fingerprint,
        point.winner_player_id,
        point.score_after,
        point.score_before,
        point.is_break_point,
        point.is_set_point,
        point.is_match_point,
        point.server_player_id,
    )


def _score_fingerprint(match: Match) -> tuple:
    live = match.live_state
    return (
        live.score if live is not None else None,
        live.server_player_id if live is not None else None,
    )


def _state_fingerprint(match: Match) -> tuple:
    live = match.live_state
    return (
        match.status,
        match.winner_player_id,
        live.connection_status if live is not None else None,
        _score_fingerprint(match),
    )


def _statistics_fingerprint(snapshot: MatchSnapshot) -> tuple:
    return tuple(
        sorted(
            (
                stat.name,
                stat.period,
                stat.player1_value,
                stat.player2_value,
                stat.availability,
                stat.unit,
            )
            for stat in snapshot.statistics
        )
    )


def reduce_live_snapshot(
    previous: MatchSnapshot | None,
    candidate: MatchSnapshot,
    *,
    momentum_engine: RecentControlEngine | None = None,
) -> LiveReduction:
    match = candidate.match
    match_id = match.id

    if previous is None:
        points = tuple(
            point.model_copy(update={"sequence": index + 1})
            for index, point in enumerate(candidate.points)
        )
        events: set[ReductionChange] = set()
        if match.live_state is not None:
            events.add(ReductionChange.SCORE_UPDATED)
        if points:
            events.add(ReductionChange.POINT_APPENDED)
        if candidate.statistics:
            events.add(ReductionChange.STATISTICS_UPDATED)
        if candidate.quality:
            events.add(ReductionChange.QUALITY_UPDATED)
        momentum = _compute_momentum(
            momentum_engine,
            match,
            points,
            state_version=1,
        )
        if momentum:
            events.add(ReductionChange.MOMENTUM_UPDATED)
        snapshot = _with_version(match, candidate, 1, points, momentum)
        return LiveReduction(
            match_id=match_id,
            previous_version=0,
            snapshot=snapshot,
            changed=True,
            events=_ordered(events),
            appended_points=points,
            point_revisions=(),
            recompute_from_sequence=None,
            statistics=candidate.statistics,
            quality=candidate.quality,
        )

    changes: set[ReductionChange] = set()
    if _state_fingerprint(match) != _state_fingerprint(previous.match):
        if _score_fingerprint(match) != _score_fingerprint(previous.match):
            changes.add(ReductionChange.SCORE_UPDATED)
        if (
            match.status != previous.match.status
            or (match.live_state.connection_status if match.live_state else None)
            != (
                previous.match.live_state.connection_status
                if previous.match.live_state
                else None
            )
        ):
            changes.add(ReductionChange.CONNECTION_UPDATED)

    previous_points = sorted(previous.points, key=lambda item: item.sequence)
    previous_by_identity = {_point_identity(item): item for item in previous_points}
    candidate_identities = {_point_identity(item) for item in candidate.points}

    appended: list[PointEvent] = []
    revisions: list[PointRevision] = []
    recompute: int | None = None
    next_sequence = (previous_points[-1].sequence + 1) if previous_points else 1

    reduced_points: list[PointEvent] = []
    for point in candidate.points:
        identity = _point_identity(point)
        stored = previous_by_identity.get(identity)
        if stored is None:
            sequenced = point.model_copy(update={"sequence": next_sequence})
            next_sequence += 1
            appended.append(sequenced)
            reduced_points.append(sequenced)
            continue
        if _point_fingerprint(point) != _point_fingerprint(stored):
            corrected = stored.model_copy(
                update={
                    "winner_player_id": point.winner_player_id,
                    "score_before": point.score_before,
                    "score_after": point.score_after,
                    "is_break_point": point.is_break_point,
                    "is_set_point": point.is_set_point,
                    "is_match_point": point.is_match_point,
                    "server_player_id": point.server_player_id,
                    "source_fingerprint": point.source_fingerprint,
                    "observed_at": point.observed_at,
                    "quality": point.quality,
                    "revision": stored.revision + 1,
                }
            )
            revisions.append(
                PointRevision(
                    point_id=stored.id,
                    sequence=stored.sequence,
                    revision=stored.revision + 1,
                    before=stored,
                    after=corrected,
                    revised_at=candidate.as_of,
                )
            )
            reduced_points.append(corrected)
            recompute = stored.sequence if recompute is None else min(recompute, stored.sequence)
        else:
            reduced_points.append(stored)

    dropped = [
        stored
        for stored in previous_points
        if _point_identity(stored) not in candidate_identities
    ]
    if dropped:
        recompute = (
            min(stored.sequence for stored in dropped)
            if recompute is None
            else min(recompute, min(stored.sequence for stored in dropped))
        )
        changes.add(ReductionChange.POINT_CORRECTED)

    # Rebuild contiguous sequences from the first difference.
    if recompute is not None:
        rebuilt: list[PointEvent] = []
        for index, point in enumerate(reduced_points):
            expected = index + 1
            rebuilt.append(
                point if point.sequence == expected else point.model_copy(update={"sequence": expected})
            )
        reduced_points = rebuilt

    if appended:
        changes.add(ReductionChange.POINT_APPENDED)
    if revisions:
        changes.add(ReductionChange.POINT_CORRECTED)
    if _statistics_fingerprint(candidate) != _statistics_fingerprint(previous):
        changes.add(ReductionChange.STATISTICS_UPDATED)
    if candidate.quality != previous.quality:
        changes.add(ReductionChange.QUALITY_UPDATED)

    momentum = previous.momentum
    if _momentum_signature(previous.points) != _momentum_signature(reduced_points):
        recomputed = _compute_momentum(
            momentum_engine,
            match,
            tuple(reduced_points),
            state_version=previous.state_version + 1,
        )
        if recomputed != previous.momentum:
            changes.add(ReductionChange.MOMENTUM_UPDATED)
        momentum = recomputed
    elif not previous.momentum and _momentum_signature(reduced_points):
        recomputed = _compute_momentum(
            momentum_engine,
            match,
            tuple(reduced_points),
            state_version=previous.state_version + 1,
        )
        if recomputed:
            changes.add(ReductionChange.MOMENTUM_UPDATED)
            momentum = recomputed

    changed = bool(changes)
    if not changed:
        return LiveReduction(
            match_id=match_id,
            previous_version=previous.state_version,
            snapshot=previous,
            changed=False,
            events=(),
            appended_points=(),
            point_revisions=(),
            recompute_from_sequence=None,
            statistics=previous.statistics,
            quality=previous.quality,
        )

    version = previous.state_version + 1
    snapshot = _with_version(match, candidate, version, tuple(reduced_points), momentum)
    return LiveReduction(
        match_id=match_id,
        previous_version=previous.state_version,
        snapshot=snapshot,
        changed=True,
        events=_ordered(changes),
        appended_points=tuple(appended),
        point_revisions=tuple(revisions),
        recompute_from_sequence=recompute,
        statistics=candidate.statistics,
        quality=candidate.quality,
    )


def _with_version(
    match: Match,
    candidate: MatchSnapshot,
    version: int,
    points: tuple[PointEvent, ...],
    momentum: tuple[MomentumObservation, ...],
) -> MatchSnapshot:
    live_state = match.live_state or LiveMatchState()
    versioned_match = match.model_copy(
        update={"live_state": live_state.model_copy(update={"state_version": version})}
    )
    return MatchSnapshot(
        match=versioned_match,
        points=points,
        statistics=candidate.statistics,
        momentum=momentum,
        quality=candidate.quality,
        state_version=version,
        as_of=candidate.as_of,
    )


def _ordered(changes: set[ReductionChange]) -> tuple[ReductionChange, ...]:
    return tuple(change for change in CHANGE_ORDER if change in changes)


def _momentum_signature(points: tuple[PointEvent, ...] | list[PointEvent]) -> tuple:
    """Return only the point inputs that can change the numeric index."""
    return tuple(
        (
            point.sequence,
            point.server_player_id,
            point.winner_player_id,
            point.observed_at,
        )
        for point in points
        if point.winner_player_id is not None
    )


def _compute_momentum(
    engine: RecentControlEngine | None,
    match: Match,
    points: tuple[PointEvent, ...],
    *,
    state_version: int,
) -> tuple[MomentumObservation, ...]:
    if not _momentum_signature(points):
        return ()
    runtime = engine or RecentControlEngine()
    return tuple(
        runtime.compute(
            points,
            focal_player_id=match.players[0].id,
            cohort=(
                match.tournament.circuit,
                match.tournament.gender,
                match.tournament.discipline,
            ),
            match_id=match.id,
            state_version=state_version,
        )
    )
