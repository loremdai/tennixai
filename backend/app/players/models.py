"""Canonical player ranking models for the P2.6 directory layer."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.domain import CapabilityStatus, CircuitTier, FrozenModel, Gender, Match, Player


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


class PlayerResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class PlayerCandidate(FrozenModel):
    player: Player
    matched_alias: str
    alias_kind: PlayerAliasKind
    current_rank: int | None = None


class PlayerResolution(FrozenModel):
    """Domain result, never an exception: ambiguous/not_found are recoverable."""

    status: PlayerResolutionStatus
    query: str
    player: Player | None = None
    candidates: tuple[PlayerCandidate, ...] = ()


class ResultOutcome(StrEnum):
    ALL = "all"
    WON = "won"
    LOST = "lost"


class SurfaceRecord(FrozenModel):
    won: int = Field(ge=0)
    lost: int = Field(ge=0)


class PlayerSeasonRecord(FrozenModel):
    season: int
    matches_won: int = Field(ge=0)
    matches_lost: int = Field(ge=0)
    titles: int = Field(ge=0)
    hard: SurfaceRecord | None = None
    clay: SurfaceRecord | None = None
    grass: SurfaceRecord | None = None


class PlayerProfileData(FrozenModel):
    player: Player
    birth_date: date | None = None
    image_url: str | None = None
    seasons: tuple[PlayerSeasonRecord, ...] = ()


class PlayerProfileView(FrozenModel):
    profile: PlayerProfileData
    selected_season: int
    season_record: PlayerSeasonRecord | None = None
    current_match: Match | None = None


# The official rankings page is bounded to the Top 200 snapshot; the wider
# directory (incl. outside-200 and unranked members) stays searchable.
RANKINGS_TOP_RANK = 200


class RankingPage(FrozenModel):
    tour: Tour
    page: int
    page_size: int
    total: int
    entries: tuple[RankingEntry, ...]
    as_of: datetime
    availability: CapabilityStatus


class PlayerResultPage(FrozenModel):
    player: Player
    season: int
    tiers: tuple[CircuitTier, ...]
    outcome: ResultOutcome
    page: int
    page_size: int
    total: int
    matches: tuple[Match, ...]
    availability: CapabilityStatus
