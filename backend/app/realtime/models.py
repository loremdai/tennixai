"""Realtime reduction models shared by the reducer, worker and persistence."""

from datetime import datetime
from enum import StrEnum

from app.domain import (
    DataQuality,
    FrozenModel,
    MatchSnapshot,
    MatchStatistic,
    PointEvent,
)


class ReductionChange(StrEnum):
    """Typed change union published inside one atomic `match_delta` (spec §11)."""

    SCORE_UPDATED = "score_updated"
    POINT_APPENDED = "point_appended"
    POINT_CORRECTED = "point_corrected"
    STATISTICS_UPDATED = "statistics_updated"
    MOMENTUM_UPDATED = "momentum_updated"
    QUALITY_UPDATED = "quality_updated"
    CONNECTION_UPDATED = "connection_updated"
    PLAYER_METADATA_UPDATED = "player_metadata_updated"


CHANGE_ORDER: tuple[ReductionChange, ...] = (
    ReductionChange.SCORE_UPDATED,
    ReductionChange.POINT_APPENDED,
    ReductionChange.POINT_CORRECTED,
    ReductionChange.STATISTICS_UPDATED,
    ReductionChange.MOMENTUM_UPDATED,
    ReductionChange.QUALITY_UPDATED,
    ReductionChange.CONNECTION_UPDATED,
    ReductionChange.PLAYER_METADATA_UPDATED,
)


class FeedDisconnected(Exception):
    """Transport-level loss of a live feed. The reason never contains
    credentials or connection URIs."""


class PointRevision(FrozenModel):
    point_id: str
    sequence: int
    revision: int
    before: PointEvent
    after: PointEvent
    revised_at: datetime
    reason: str = "provider_correction"


class LiveReduction(FrozenModel):
    """Result of reducing one supplier snapshot against the previous state."""

    match_id: str
    previous_version: int
    snapshot: MatchSnapshot
    changed: bool
    events: tuple[ReductionChange, ...] = ()
    appended_points: tuple[PointEvent, ...] = ()
    point_revisions: tuple[PointRevision, ...] = ()
    recompute_from_sequence: int | None = None
    statistics: tuple[MatchStatistic, ...] = ()
    quality: tuple[DataQuality, ...] = ()
