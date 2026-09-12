from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    UNKNOWN = "unknown"


class CircuitTier(StrEnum):
    ATP = "atp"
    WTA = "wta"
    CHALLENGER = "challenger"
    ITF = "itf"
    OTHER = "other"


class Gender(StrEnum):
    MEN = "men"
    WOMEN = "women"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class Discipline(StrEnum):
    SINGLES = "singles"
    DOUBLES = "doubles"
    TEAM = "team"
    UNKNOWN = "unknown"


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    LIVE = "live"
    RECONNECTING = "reconnecting"
    STALE = "stale"
    ENDED = "ended"
    UNAVAILABLE = "unavailable"


class CapabilityStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


class StatisticName(StrEnum):
    ACES = "aces"
    DOUBLE_FAULTS = "double_faults"
    FIRST_SERVE_PERCENTAGE = "first_serve_percentage"
    FIRST_SERVE_POINTS_WON = "first_serve_points_won"
    SECOND_SERVE_POINTS_WON = "second_serve_points_won"
    SERVICE_POINTS_WON = "service_points_won"
    SERVICE_GAMES_WON = "service_games_won"
    BREAK_POINTS_SAVED = "break_points_saved"
    BREAK_POINTS_CONVERTED = "break_points_converted"
    RETURN_POINTS_WON = "return_points_won"
    FIRST_RETURN_POINTS_WON = "first_return_points_won"
    SECOND_RETURN_POINTS_WON = "second_return_points_won"
    RETURN_GAMES_WON = "return_games_won"
    WINNERS = "winners"
    UNFORCED_ERRORS = "unforced_errors"
    NET_POINTS_WON = "net_points_won"
    TOTAL_POINTS_WON = "total_points_won"
    TOTAL_GAMES_WON = "total_games_won"
    MATCH_POINTS_SAVED = "match_points_saved"
    AVERAGE_FIRST_SERVE_SPEED = "average_first_serve_speed"
    AVERAGE_SECOND_SERVE_SPEED = "average_second_serve_speed"
    DISTANCE_COVERED = "distance_covered"


class StatisticProvenance(StrEnum):
    PROVIDER = "provider"
    DERIVED_PBP = "derived_pbp"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DataFreshness(FrozenModel):
    provider: str
    source_updated_at: datetime | None = None
    observed_at: datetime
    is_stale: bool = False
    age_seconds: int = 0

    @field_validator("source_updated_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class Player(FrozenModel):
    id: str
    name: str
    localized_name: str | None = None
    country_code: str | None = None
    ranking: int | None = None


class Tournament(FrozenModel):
    id: str
    name: str
    tour: str | None = None
    circuit: CircuitTier = CircuitTier.OTHER
    gender: Gender = Gender.UNKNOWN
    discipline: Discipline = Discipline.UNKNOWN


class SetScore(FrozenModel):
    number: int
    player1_games: int | None = None
    player2_games: int | None = None


class MatchScore(FrozenModel):
    sets_won: tuple[int, int]
    sets: tuple[SetScore, ...]
    points: tuple[str | None, str | None] = (None, None)
    is_tiebreak: bool = False


class LiveMatchState(FrozenModel):
    score: MatchScore | None = None
    server_player_id: str | None = None
    state_version: int = Field(default=0, ge=0)
    connection_status: ConnectionStatus = ConnectionStatus.UNAVAILABLE
    last_event_at: datetime | None = None
    as_of: datetime | None = None

    @field_validator("last_event_at", "as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class Match(FrozenModel):
    id: str
    status: MatchStatus
    players: tuple[Player, Player]
    tournament: Tournament
    scheduled_at: datetime | None = None
    round: str | None = None
    surface: str | None = None
    indoor: bool | None = None
    format: str | None = None
    live_state: LiveMatchState | None = None
    winner_player_id: str | None = None
    freshness: DataFreshness

    @field_validator("scheduled_at")
    @classmethod
    def require_scheduled_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("scheduled_at must be timezone-aware")
        return value


class DataQuality(FrozenModel):
    """Capability-level availability. Never carries a value: missing data is
    declared, not defaulted to zero."""

    capability: str
    status: CapabilityStatus
    provider: str
    reason: str | None = None
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class PointEvent(FrozenModel):
    id: str
    match_id: str
    sequence: int = Field(ge=1)
    set_number: int = Field(ge=1)
    game_number: int = Field(ge=1)
    point_number: int = Field(ge=1)
    server_player_id: str | None = None
    winner_player_id: str | None = None
    score_before: MatchScore | None = None
    score_after: MatchScore
    is_break_point: bool = False
    is_set_point: bool = False
    is_match_point: bool = False
    observed_at: datetime
    provider: str
    source_fingerprint: str
    revision: int = Field(default=1, ge=1)
    quality: DataQuality | None = None

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class MatchStatistic(FrozenModel):
    match_id: str
    name: StatisticName
    period: str = "match"
    player1_value: float | None = None
    player2_value: float | None = None
    unit: str | None = None
    provenance: StatisticProvenance = StatisticProvenance.PROVIDER
    availability: CapabilityStatus
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class MomentumObservation(FrozenModel):
    match_id: str
    point_sequence: int = Field(ge=1)
    state_version: int = Field(ge=0)
    algorithm_version: str
    value: float = Field(ge=-100.0, le=100.0)
    leader_player_id: str | None = None
    is_provisional: bool = False
    as_of: datetime
    input_summary: str

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class HeadToHead(FrozenModel):
    first_player_id: str
    second_player_id: str
    meetings: tuple[Match, ...] = ()
    first_player_recent: tuple[Match, ...] = ()
    second_player_recent: tuple[Match, ...] = ()
    freshness: DataFreshness


class MatchSnapshot(FrozenModel):
    """Full canonical view of one match. `match.live_state` is the single
    live-state source; the top-level version must agree with it."""

    match: Match
    points: tuple[PointEvent, ...] = ()
    statistics: tuple[MatchStatistic, ...] = ()
    momentum: tuple[MomentumObservation, ...] = ()
    quality: tuple[DataQuality, ...] = ()
    state_version: int = Field(ge=0)
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_version_and_ownership(self) -> "MatchSnapshot":
        live_state = self.match.live_state
        expected_version = live_state.state_version if live_state is not None else 0
        if self.state_version != expected_version:
            raise ValueError(
                "state_version must equal match.live_state.state_version "
                f"({expected_version}), got {self.state_version}"
            )
        for point in self.points:
            if point.match_id != self.match.id:
                raise ValueError(
                    f"point {point.id} belongs to match {point.match_id}, "
                    f"not {self.match.id}"
                )
        for observation in self.momentum:
            if observation.match_id != self.match.id:
                raise ValueError(
                    f"momentum observation belongs to match {observation.match_id}, "
                    f"not {self.match.id}"
                )
        for statistic in self.statistics:
            if statistic.match_id != self.match.id:
                raise ValueError(
                    f"statistic {statistic.name} belongs to match {statistic.match_id}, "
                    f"not {self.match.id}"
                )
        return self
