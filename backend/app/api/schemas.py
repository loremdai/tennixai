from typing import Any

from pydantic import BaseModel, Field

from app.domain import Match, Player


class PlayerListResponse(BaseModel):
    data: list[Player]


class MatchListResponse(BaseModel):
    data: list[Match]


class MatchResponse(BaseModel):
    data: Match


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str
