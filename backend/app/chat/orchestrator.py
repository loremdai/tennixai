"""Chat orchestrator: historical guard, bounded tool loop, data-first fallback.

Event order is fixed: status → data → text_delta → done. Structured data is
always emitted before generated prose so the UI can render trusted cards even
when the model later fails.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from app.chat.client import ChatModel
from app.chat.models import (
    ChatContext,
    ChatEvent,
    ChatEventType,
    ChatRequest,
    ChatScope,
    StructuredToolResult,
)
from app.chat.tools import BusinessTools, is_unsupported_historical_query
from app.domain import Match
from app.errors import AppError

HISTORICAL_REPLY = "P2 暂不支持大范围历史查询。"
LLM_FALLBACK_REPLY = "比赛数据已找到，但 AI 说明暂时不可用。"
MAX_TOOL_ROUNDS = 2
MAX_MODEL_MATCHES = 12

GLOBAL_SYSTEM_PROMPT = (
    "你是 TennixAI 的网球比赛信息助手。"
    "所有网球事实（比分、赛程、球员、赛事、状态、发球方、ID、时间）必须来自工具结果，不得凭记忆编造。"
    "禁止输出任何外部供应商 ID；只使用工具返回的 Tennix 内部 ID。"
    "工具未提供的字段必须如实说明暂不可用。"
    "昨天、最近有限场结果和两位球员的有限交手记录使用对应 P2 工具；大范围历史查询不支持。"
    "Match scope 的主题问题使用 get_match_intelligence，topic 只能是 overview、score、statistics、points 或 momentum。"
)
MATCH_SYSTEM_SUFFIX = (
    "当前比赛已由页面上下文确定（current match id: {match_id}），"
    "所有上下文事实问题先调用 get_match_intelligence，调用 get_match 时无需提供参数。"
)


def _model_match_summary(match: Match) -> dict[str, Any]:
    player_names = {player.id: player.name for player in match.players}
    score = None
    if match.live_state is not None and match.live_state.score is not None:
        match_score = match.live_state.score
        score = {
            "sets_won": list(match_score.sets_won),
            "sets": [
                {
                    "number": set_score.number,
                    "player1_games": set_score.player1_games,
                    "player2_games": set_score.player2_games,
                }
                for set_score in match_score.sets
            ],
            "points": list(match_score.points),
            "is_tiebreak": match_score.is_tiebreak,
        }

    return {
        "id": match.id,
        "status": match.status.value,
        "players": [player.name for player in match.players],
        "tournament": match.tournament.name,
        "scheduled_at": match.scheduled_at.isoformat() if match.scheduled_at else None,
        "round": match.round,
        "surface": match.surface,
        "indoor": match.indoor,
        "format": match.format,
        "score": score,
        "server_player": (
            player_names.get(match.live_state.server_player_id)
            if match.live_state is not None
            else None
        ),
        "winner_player": player_names.get(match.winner_player_id),
        "is_stale": match.freshness.is_stale,
    }


def _model_tool_result(result: StructuredToolResult) -> dict[str, Any]:
    matches = result.matches
    payload: dict[str, Any] = {
        "kind": result.kind,
        "match_count": len(matches),
        "truncated": len(matches) > MAX_MODEL_MATCHES,
        "matches": [_model_match_summary(match) for match in matches[:MAX_MODEL_MATCHES]],
    }
    if result.packet is not None:
        payload["packet"] = result.packet.model_dump(mode="json")
    if result.metadata:
        payload["metadata"] = result.metadata
    if result.answer_context is not None:
        payload["answer_context"] = result.answer_context.model_dump(mode="json")
    return payload


class ChatOrchestrator:
    def __init__(self, tools: BusinessTools, model: ChatModel) -> None:
        self._tools = tools
        self._model = model

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        if request.scope is ChatScope.MATCH and not request.match_id:
            yield ChatEvent(
                type=ChatEventType.ERROR,
                payload={
                    "code": "invalid_request",
                    "message": "match_id is required for match scope",
                    "details": {},
                },
            )
            return

        last_user = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role == "user"
            ),
            "",
        )
        if is_unsupported_historical_query(last_user):
            unsupported = StructuredToolResult(kind="unsupported")
            yield ChatEvent(
                type=ChatEventType.DATA, payload=unsupported.model_dump(mode="json")
            )
            yield ChatEvent(
                type=ChatEventType.TEXT_DELTA, payload={"delta": HISTORICAL_REPLY}
            )
            yield ChatEvent(type=ChatEventType.DONE, payload={"ok": True})
            return

        yield ChatEvent(type=ChatEventType.STATUS, payload={"stage": "resolving"})

        context = ChatContext(scope=request.scope, match_id=request.match_id)
        system = GLOBAL_SYSTEM_PROMPT
        if request.scope is ChatScope.MATCH:
            system = f"{system}\n{MATCH_SYSTEM_SUFFIX.format(match_id=request.match_id)}"

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in request.messages
        )

        data_emitted = False
        rounds = 0
        catalog = self._tools.catalog()

        try:
            while True:
                turn = await self._model.choose(messages, catalog)
                if not turn.tool_calls:
                    break
                rounds += 1
                if rounds > MAX_TOOL_ROUNDS:
                    raise AppError(
                        "invalid_request", "Too many tool-call rounds requested", 422
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": json.dumps(
                                        call.arguments, ensure_ascii=False
                                    ),
                                },
                            }
                            for call in turn.tool_calls
                        ],
                    }
                )
                for call in turn.tool_calls:
                    result = await self._tools.execute(call.name, call.arguments, context)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                _model_tool_result(result), ensure_ascii=False
                            ),
                        }
                    )
                    yield ChatEvent(
                        type=ChatEventType.DATA, payload=result.model_dump(mode="json")
                    )
                    data_emitted = True
        except AppError as error:
            yield ChatEvent(
                type=ChatEventType.ERROR,
                payload={
                    "code": error.code,
                    "message": error.message,
                    "details": error.details,
                },
            )
            return

        try:
            async for chunk in self._model.stream_text(messages):
                yield ChatEvent(type=ChatEventType.TEXT_DELTA, payload={"delta": chunk})
        except Exception:
            if data_emitted:
                yield ChatEvent(
                    type=ChatEventType.TEXT_DELTA, payload={"delta": LLM_FALLBACK_REPLY}
                )
            yield ChatEvent(
                type=ChatEventType.ERROR,
                payload={
                    "code": "llm_unavailable",
                    "message": "LLM streaming failed",
                    "details": {},
                },
            )
            return

        yield ChatEvent(type=ChatEventType.DONE, payload={"ok": True})
