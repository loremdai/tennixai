from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain import Match, MatchSnapshot, Player
from app.players.models import (
    PlayerProfileView,
    PlayerResolution,
    PlayerResultPage,
    RankingPage,
)
from app.service import HeadToHeadResult, MatchCatalog, PlayerResults


class PlayerListResponse(BaseModel):
    data: list[Player]


class RankingPageResponse(BaseModel):
    data: RankingPage


class PlayerResolutionResponse(BaseModel):
    data: PlayerResolution


class PlayerProfileViewResponse(BaseModel):
    data: PlayerProfileView


class PlayerResultPageResponse(BaseModel):
    data: PlayerResultPage


class MatchListResponse(BaseModel):
    data: list[Match]


class MatchResponse(BaseModel):
    data: Match


class MatchSnapshotResponse(BaseModel):
    data: MatchSnapshot


class MatchCatalogResponse(BaseModel):
    data: MatchCatalog


class PlayerResultsResponse(BaseModel):
    data: PlayerResults


class HeadToHeadResultResponse(BaseModel):
    data: HeadToHeadResult


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str


# ---------------------------------------------------------------------------
# P3 read-only public DTOs (T66). Internal IDs only; provider identifiers,
# wallet material and raw payloads never appear here.
# ---------------------------------------------------------------------------


class OpportunityDto(BaseModel):
    match_id: str
    market_id: str
    phase: str  # "live" | "upcoming"
    action: str  # "buy" | "wait"
    target_player_id: str | None = None
    player_names: tuple[str, str] | None = None
    model_probability: float | None = None
    executable_probability: float | None = None
    conservative_net_edge: str | None = None
    max_acceptable_price: str | None = None
    tournament_tier: str | None = None
    tournament_name: str | None = None
    as_of: datetime | None = None


class MarketSummaryDto(BaseModel):
    market_id: str
    match_id: str | None = None
    question: str | None = None
    status: str
    tier: str | None = None
    gender: str | None = None
    phase: str | None = None
    model_covered: bool = False
    action: str | None = None
    reason_code: str | None = None
    best_bid: tuple[str, str] | None = None
    best_ask: tuple[str, str] | None = None
    as_of: datetime | None = None


class MarketPageDto(BaseModel):
    markets: list[MarketSummaryDto]
    page: int = 1
    page_size: int = 20
    total: int = 0


class PaperPositionDto(BaseModel):
    position_id: str
    match_id: str
    market_id: str
    outcome_player_id: str
    player_names: tuple[str, str] | None = None
    status: str
    entry_cost: str
    shares: str
    current_exit_value: str | None = None
    net_pnl: str | None = None
    freshness_as_of: datetime | None = None


class PulseRowDto(BaseModel):
    match_id: str
    market_id: str | None = None
    kind: str  # "position" | "opportunity"
    action: str
    player_names: tuple[str, str] | None = None
    model_probability: float | None = None
    executable_probability: float | None = None
    as_of: datetime | None = None


class PositionSummaryDto(BaseModel):
    position_id: str
    outcome_player_id: str
    status: str
    entry_cost: str
    shares: str


class DecisionSnapshotDto(BaseModel):
    match_id: str
    market_id: str | None = None
    action: str
    reason_code: str | None = None
    observation_version: int
    model_probabilities: dict[str, float] | None = None
    model_availability: str | None = None
    quote_average_price: str | None = None
    quote_side: str | None = None
    conservative_net_edge: str | None = None
    position: PositionSummaryDto | None = None
    lifecycle: tuple[str, ...] = ()
    is_stale: bool = False
    has_gap: bool = False
    lock_profit_available: bool = False
    as_of: datetime | None = None


class OpportunityListResponse(BaseModel):
    data: list[OpportunityDto]


class MarketListResponse(BaseModel):
    data: list[MarketSummaryDto]
    page: int
    page_size: int
    total: int


class PaperPositionsResponse(BaseModel):
    open: list[PaperPositionDto]
    recent: list[PaperPositionDto]


class PulseResponse(BaseModel):
    data: list[PulseRowDto]
    has_open_position: bool


class MatchDecisionResponse(BaseModel):
    data: DecisionSnapshotDto
