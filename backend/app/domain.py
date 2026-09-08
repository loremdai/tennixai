from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    UNKNOWN = "unknown"


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
    country_code: str | None = None
    ranking: int | None = None


class Tournament(FrozenModel):
    id: str
    name: str
    tour: str | None = None


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
