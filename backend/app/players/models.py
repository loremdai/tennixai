"""Canonical player ranking models for the P2.6 directory layer."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.domain import FrozenModel, Player


class Tour(StrEnum):
    ATP = "ATP"
    WTA = "WTA"


class RankingMovement(StrEnum):
    UP = "up"
    DOWN = "down"
    SAME = "same"
    UNKNOWN = "unknown"


class RankingEntry(FrozenModel):
    player: Player
    tour: Tour
    rank: int = Field(ge=1)
    points: int = Field(ge=0)
    movement: RankingMovement
    ranking_date: date
    fetched_at: datetime

    @field_validator("fetched_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value
