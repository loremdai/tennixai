"""Topic-scoped, compact canonical facts for the P2 Chat tools.

The packet deliberately uses names and derived facts instead of provider rows,
point identifiers, fingerprints, or provider names. It is an explanation
input, not a second snapshot model and not a place for the LLM to calculate
new values.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain import CapabilityStatus, MatchScore, MatchSnapshot, StatisticProvenance


class IntelligenceTopic(StrEnum):
    OVERVIEW = "overview"
    SCORE = "score"
    STATISTICS = "statistics"
    POINTS = "points"
    MOMENTUM = "momentum"


class IntelligenceStatistic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    period: str
    player1_value: float | None
    player2_value: float | None
    unit: str | None
    provenance: StatisticProvenance
    availability: CapabilityStatus
    as_of: datetime


class IntelligencePoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    set_number: int = Field(ge=1)
    game_number: int = Field(ge=1)
    point_number: int = Field(ge=1)
    server: str | None
    winner: str | None
    score_after: MatchScore
    is_break_point: bool
    is_set_point: bool
    is_match_point: bool


class IntelligenceKeyPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    labels: tuple[str, ...]
    winner: str | None


class IntelligenceMomentum(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    point_sequence: int = Field(ge=1)
    algorithm_version: str
    value: float = Field(ge=-100.0, le=100.0)
    leader: str | None
    is_provisional: bool
    as_of: datetime
    input_summary: str


class IntelligenceQuality(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: str
    status: CapabilityStatus
    reason: str | None
    observed_at: datetime


class IntelligencePacket(BaseModel):
    """Bounded canonical facts selected for one intelligence topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: IntelligenceTopic
    match_id: str
    state_version: int = Field(ge=0)
    as_of: datetime
    status: str
    players: tuple[str, str]
    tournament: str
    round: str | None
    scheduled_at: datetime | None
    surface: str | None
    indoor: bool | None
    format: str | None
    winner: str | None
    score: MatchScore | None
    server: str | None
    statistics: tuple[IntelligenceStatistic, ...] = ()
    recent_points: tuple[IntelligencePoint, ...] = ()
    momentum: tuple[IntelligenceMomentum, ...] = ()
    key_points: tuple[IntelligenceKeyPoint, ...] = ()
    quality: tuple[IntelligenceQuality, ...] = ()


def build_intelligence_packet(
    snapshot: MatchSnapshot,
    *,
    topic: IntelligenceTopic | str,
) -> IntelligencePacket:
    selected_topic = IntelligenceTopic(topic)
    match = snapshot.match
    player_names = {player.id: player.name for player in match.players}
    live_state = match.live_state

    def name_for(player_id: str | None) -> str | None:
        return player_names.get(player_id) if player_id is not None else None

    determinate_points = sorted(
        (point for point in snapshot.points if point.winner_player_id is not None),
        key=lambda point: point.sequence,
    )
    recent_source = determinate_points[-20:]
    recent_points = tuple(
        IntelligencePoint(
            sequence=point.sequence,
            set_number=point.set_number,
            game_number=point.game_number,
            point_number=point.point_number,
            server=name_for(point.server_player_id),
            winner=name_for(point.winner_player_id),
            score_after=point.score_after,
            is_break_point=point.is_break_point,
            is_set_point=point.is_set_point,
            is_match_point=point.is_match_point,
        )
        for point in recent_source
    )
    recent_start = recent_source[0].sequence if recent_source else None
    recent_end = recent_source[-1].sequence if recent_source else None
    key_point_source = [
        point
        for point in sorted(snapshot.points, key=lambda item: item.sequence)
        if (recent_start is None or point.sequence >= recent_start)
        and (recent_end is None or point.sequence <= recent_end)
        and (point.is_break_point or point.is_set_point or point.is_match_point)
    ]
    key_points = tuple(
        IntelligenceKeyPoint(
            sequence=point.sequence,
            labels=tuple(
                label
                for label, enabled in (
                    ("break_point", point.is_break_point),
                    ("set_point", point.is_set_point),
                    ("match_point", point.is_match_point),
                )
                if enabled
            ),
            winner=name_for(point.winner_player_id),
        )
        for point in key_point_source[-20:]
    )

    statistics = tuple(
        IntelligenceStatistic(
            name=statistic.name.value,
            period=statistic.period,
            player1_value=statistic.player1_value,
            player2_value=statistic.player2_value,
            unit=statistic.unit,
            provenance=statistic.provenance,
            availability=statistic.availability,
            as_of=statistic.as_of,
        )
        for statistic in snapshot.statistics
    )

    momentum_source = sorted(snapshot.momentum, key=lambda item: item.point_sequence)
    if momentum_source:
        latest_algorithm = momentum_source[-1].algorithm_version
        momentum_source = [
            item for item in momentum_source if item.algorithm_version == latest_algorithm
        ]
    momentum = tuple(
        IntelligenceMomentum(
            point_sequence=observation.point_sequence,
            algorithm_version=observation.algorithm_version,
            value=observation.value,
            leader=name_for(observation.leader_player_id),
            is_provisional=observation.is_provisional,
            as_of=observation.as_of,
            input_summary=observation.input_summary,
        )
        for observation in momentum_source[-20:]
    )

    quality = tuple(
        IntelligenceQuality(
            capability=item.capability,
            status=item.status,
            reason=item.reason,
            observed_at=item.observed_at,
        )
        for item in snapshot.quality
    )

    include_statistics = selected_topic is IntelligenceTopic.STATISTICS
    include_points = selected_topic in {
        IntelligenceTopic.POINTS,
        IntelligenceTopic.MOMENTUM,
    }
    include_momentum = selected_topic is IntelligenceTopic.MOMENTUM
    include_score = selected_topic in {
        IntelligenceTopic.OVERVIEW,
        IntelligenceTopic.SCORE,
    }
    return IntelligencePacket(
        topic=selected_topic,
        match_id=match.id,
        state_version=snapshot.state_version,
        as_of=snapshot.as_of,
        status=match.status.value,
        players=(match.players[0].name, match.players[1].name),
        tournament=match.tournament.name,
        round=match.round,
        scheduled_at=match.scheduled_at,
        surface=match.surface,
        indoor=match.indoor,
        format=match.format,
        winner=name_for(match.winner_player_id),
        score=live_state.score if include_score and live_state is not None else None,
        server=(
            name_for(live_state.server_player_id)
            if include_score and live_state is not None
            else None
        ),
        statistics=statistics if include_statistics else (),
        recent_points=recent_points if include_points else (),
        momentum=momentum if include_momentum else (),
        key_points=key_points if include_points else (),
        quality=quality,
    )


__all__ = [
    "IntelligenceKeyPoint",
    "IntelligenceMomentum",
    "IntelligencePacket",
    "IntelligencePoint",
    "IntelligenceQuality",
    "IntelligenceStatistic",
    "IntelligenceTopic",
    "build_intelligence_packet",
]
