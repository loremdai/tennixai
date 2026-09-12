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
