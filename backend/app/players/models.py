"""Canonical player ranking models for the P2.6 directory layer."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.domain import FrozenModel, Gender, Player


class Tour(StrEnum):
    ATP = "ATP"
    WTA = "WTA"


class RankingMovement(StrEnum):
    UP = "up"
    DOWN = "down"
    SAME = "same"
    UNKNOWN = "unknown"


class PlayerAliasKind(StrEnum):
    PREFERRED = "preferred"
    FULL = "full"
    SURNAME = "surname"
    REORDERED = "reordered"
    ABBREVIATED = "abbreviated"
    PROVIDER = "provider"
    TRANSLITERATED = "transliterated"


class PlayerAliasSource(StrEnum):
    PROVIDER = "provider"
    TRUSTED_EXTERNAL = "trusted_external"
    LLM = "llm"
    DERIVED = "derived"


class PlayerAlias(FrozenModel):
    player_id: str
    locale: str
    alias: str
    normalized_alias: str
    kind: PlayerAliasKind
    source: PlayerAliasSource
    source_ref: str | None = None
    model: str | None = None
    prompt_version: str | None = None


class DirectoryPlayer(FrozenModel):
    player: Player
    gender: Gender = Gender.UNKNOWN
    birth_date: date | None = None
    image_url: str | None = None


class AliasMatch(FrozenModel):
    player: DirectoryPlayer
    alias: PlayerAlias
    current_rank: int | None = None


class LocalizedNameUpdate(FrozenModel):
    player_id: str
    localized_name: str
    aliases: tuple[PlayerAlias, ...] = ()


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
