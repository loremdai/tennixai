import json
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain import Match, MatchSnapshot
from app.intelligence import IntelligencePacket, IntelligenceTopic
from app.players.models import PlayerResolution
from app.service import MatchTimeScope, PlayerResultsScope


class ChatScope(StrEnum):
    GLOBAL = "global"
    MATCH = "match"


class ToolRequiredness(StrEnum):
    CORE = "core"
    OPTIONAL = "optional"


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
    snapshot: MatchSnapshot | None = None


class AnswerContext(BaseModel):
    match_id: str
    state_version: int = Field(ge=0)
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class StructuredToolResult(BaseModel):
    kind: Literal["matches", "match", "intelligence", "player_resolution", "unsupported"]
    matches: list[Match] = Field(default_factory=list)
    packet: IntelligencePacket | None = None
    resolution: PlayerResolution | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    answer_context: AnswerContext | None = None


class FindPlayerMatchesArgs(BaseModel):
    player_name: str = Field(min_length=1)
    time_scope: MatchTimeScope


class GetLiveMatchesArgs(BaseModel):
    player_name: str | None = None


class GetMatchArgs(BaseModel):
    match_id: str | None = None


class GetMatchIntelligenceArgs(BaseModel):
    topic: IntelligenceTopic


class GetPlayerResultsArgs(BaseModel):
    player_name: str = Field(min_length=1)
    scope: PlayerResultsScope
    limit: int = Field(default=5, ge=1, le=10)


class GetHeadToHeadArgs(BaseModel):
    first_player_name: str = Field(min_length=1)
    second_player_name: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=10)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object]


class ModelTurn(BaseModel):
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ToolOutcomeStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    REJECTED = "rejected"


class ToolOutcome(BaseModel):
    tool_name: str
    call_id: str
    status: ToolOutcomeStatus
    requiredness: ToolRequiredness
    result: StructuredToolResult | None = None
    code: str | None = None
    reason: str | None = None
    retryable: bool = False
    duration_ms: int = Field(ge=0)
    duplicate_of: str | None = None


class ChatEventType(StrEnum):
    STATUS = "status"
    DATA = "data"
    WARNING = "warning"
    TEXT_DELTA = "text_delta"
    DONE = "done"
    ERROR = "error"


class ChatEvent(BaseModel):
    type: ChatEventType
    payload: dict[str, object]

    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.payload, ensure_ascii=False)}\n\n"


__all__ = [
    "AnswerContext",
    "ChatContext",
    "ChatEvent",
    "ChatEventType",
    "ChatMessage",
    "ChatRequest",
    "ChatScope",
    "FindPlayerMatchesArgs",
    "GetLiveMatchesArgs",
    "GetMatchArgs",
    "GetMatchIntelligenceArgs",
    "GetPlayerResultsArgs",
    "GetHeadToHeadArgs",
    "IntelligenceTopic",
    "MatchTimeScope",
    "ModelTurn",
    "StructuredToolResult",
    "ToolCall",
    "ToolOutcome",
    "ToolOutcomeStatus",
    "ToolRequiredness",
]
