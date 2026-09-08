from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import Match
from app.service import MatchTimeScope


class ChatScope(StrEnum):
    GLOBAL = "global"
    MATCH = "match"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    scope: ChatScope
    match_id: str | None = None
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)


class ChatContext(BaseModel):
    scope: ChatScope
    match_id: str | None = None


class StructuredToolResult(BaseModel):
    kind: Literal["matches", "match", "unsupported"]
    matches: list[Match] = Field(default_factory=list)


class FindPlayerMatchesArgs(BaseModel):
    player_name: str = Field(min_length=1)
    time_scope: MatchTimeScope


class GetLiveMatchesArgs(BaseModel):
    player_name: str | None = None


class GetMatchArgs(BaseModel):
    match_id: str | None = None


__all__ = [
    "ChatContext",
    "ChatMessage",
    "ChatRequest",
    "ChatScope",
    "FindPlayerMatchesArgs",
    "GetLiveMatchesArgs",
    "GetMatchArgs",
    "MatchTimeScope",
    "StructuredToolResult",
]
