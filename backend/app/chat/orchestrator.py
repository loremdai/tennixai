"""Chat orchestrator: historical guard, bounded tool loop, data-first fallback.

Status events expose the phases before and during model work. Structured data
is always emitted before generated prose so the UI can render trusted cards
even when the model later fails.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from app.chat.client import ChatModel
from app.chat.capabilities import ChatPhase, ToolRequiredness, allowed_tool_names
from app.chat.executor import ToolBatchExecutor
from app.chat.models import (
    ChatContext,
    ChatEvent,
    ChatEventType,
    ChatRequest,
    ChatScope,
    StructuredToolResult,
    ToolOutcome,
    ToolOutcomeStatus,
)
from app.chat.tools import (
    BusinessTools,
    is_historical_query,
    is_unsupported_historical_query,
)
from app.domain import Match
from app.errors import AppError

HISTORICAL_REPLY = "P2 暂不支持大范围历史查询。"
LLM_FALLBACK_REPLY = "比赛数据已找到，但 AI 说明暂时不可用。"
LLM_EMPTY_REPLY = "暂时没有生成可展示的回答，请稍后重试。"
MAX_TOOL_ROUNDS = 3
MAX_REPLANS = 1
MAX_MODEL_MATCHES = 12

GLOBAL_SYSTEM_PROMPT = (
    "你是 TennixAI 的网球比赛信息助手。"
    "所有网球事实（比分、赛程、球员、赛事、状态、发球方、ID、时间）必须来自工具结果，不得凭记忆编造。"
    "禁止输出任何外部供应商 ID；只使用工具返回的 Tennix 内部 ID。"
    "工具未提供的字段必须如实说明暂不可用。"
    "本场综合分析只能使用比赛快照和工具返回的事实；球员特点或历史资料未提供时说明暂未提供，不要让可选资料缺失中止已有分析。"
    "昨天、最近有限场结果和两位球员的有限交手记录使用对应 P2 工具；大范围历史查询不支持。"
    "Match scope 的主题问题使用 get_match_intelligence，topic 只能是 overview、score、statistics、points 或 momentum。"
    "趋势和控制指数只能做描述性分析，不得编造赔率、概率或确定性的胜负结论。"
)
MATCH_SYSTEM_SUFFIX = (
    "当前比赛已由页面上下文确定（current match id: {match_id}），"
    "本次问答以提问开始时冻结的同一份比赛快照为事实基线；所有上下文事实问题先调用 get_match_intelligence，"
    "综合问题可按需调用 overview、score、statistics、points、momentum，调用 get_match 时无需提供参数，"
    "不要用回答期间的新版本覆盖或否定这份基线。"
)

MATCH_HISTORY_PHRASES = (
    "近期",
    "recent",
    "交手",
    "对战",
    "h2h",
    "head-to-head",
    "head to head",
    "球员特点",
    "球员背景",
    "近期状态",
    "近期表现",
    "优缺点",
    "strengths",
    "weaknesses",
)


def _requests_match_history(text: str) -> bool:
    normalized = text.casefold()
    return is_historical_query(text) or any(
        phrase in normalized for phrase in MATCH_HISTORY_PHRASES
    )


def _catalog_for_request(
    tools: list[dict[str, Any]],
    request: ChatRequest,
    last_user: str,
    *,
    phase: ChatPhase | None = None,
    has_discovered_matches: bool = False,
) -> list[dict[str, Any]]:
    phase = phase or (
        ChatPhase.CONTEXT if request.scope is ChatScope.MATCH else ChatPhase.DISCOVERY
    )
    allowed = set(
        allowed_tool_names(
            request.scope,
            phase,
            history_requested=_requests_match_history(last_user),
            has_discovered_matches=has_discovered_matches,
        )
    )
    return [
        item
        for item in tools
        if item.get("function", {}).get("name") in allowed
    ]


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


def _model_tool_outcome(outcome: ToolOutcome) -> dict[str, Any]:
    if outcome.result is not None and outcome.status in {
        ToolOutcomeStatus.SUCCESS,
        ToolOutcomeStatus.PARTIAL,
    }:
        return _model_tool_result(outcome.result)
    if outcome.status is ToolOutcomeStatus.REJECTED:
        return {
            "kind": "rejected",
            "tool": outcome.tool_name,
            "code": outcome.code,
            "reason": outcome.reason,
        }
    return {
        "kind": "unavailable",
        "tool": outcome.tool_name,
        "code": outcome.code,
    }


def _synthesis_messages(
    messages: list[dict[str, Any]], verified_facts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    clean_messages = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in messages
        if message.get("role") in {"system", "user", "assistant"}
        and "tool_calls" not in message
        and isinstance(message.get("content"), str)
        and message["content"]
    ]
    clean_messages.append(
        {
            "role": "user",
            "content": (
                "现在请直接回答原问题，不要调用工具。以下是提问时冻结并已核验的事实；"
                "只能根据这些事实回答，缺失字段请明确说明：\n"
                f"{json.dumps(verified_facts, ensure_ascii=False)}"
            ),
        }
    )
    return clean_messages


def _optional_warning(outcome: ToolOutcome) -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "optional_data_unavailable",
            "message": "部分辅助资料暂未提供，已继续使用可用的比赛事实。",
            "details": {
                "tool": outcome.tool_name,
                "reason": outcome.reason,
            },
        },
    )


def _replan_warning() -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "tool_replan_exhausted",
            "message": "部分辅助资料未能读取，已继续使用可用的比赛事实。",
            "details": {},
        },
    )


def _empty_generation_warning() -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "llm_empty_response",
            "message": "AI 未返回可展示的文字，已保留结构化结果。",
            "details": {},
        },
    )


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

        phase = ChatPhase.CONTEXT if request.scope is ChatScope.MATCH else ChatPhase.DISCOVERY
        yield ChatEvent(
            type=ChatEventType.STATUS,
            payload={"stage": "resolving", "phase": phase.value},
        )

        context = ChatContext(scope=request.scope, match_id=request.match_id)
        try:
            context = await self._tools.freeze_match_context(context)
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
        yield ChatEvent(
            type=ChatEventType.STATUS,
            payload={"stage": "planning", "phase": phase.value},
        )
        system = GLOBAL_SYSTEM_PROMPT
        if request.scope is ChatScope.MATCH:
            system = f"{system}\n{MATCH_SYSTEM_SUFFIX.format(match_id=request.match_id)}"

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in request.messages
        )

        data_emitted = False
        core_data_emitted = False
        rounds = 0
        executor = ToolBatchExecutor(self._tools, context)
        known_match_ids = {request.match_id} if request.match_id else set()
        has_discovered_matches = bool(known_match_ids)
        replan_count = 0
        verified_facts: list[dict[str, Any]] = []

        try:
            while True:
                catalog = _catalog_for_request(
                    self._tools.catalog(scope=request.scope),
                    request,
                    last_user,
                    phase=phase,
                    has_discovered_matches=has_discovered_matches,
                )
                turn = await self._model.choose(
                    messages,
                    catalog,
                    parallel_tool_calls=phase
                    in {ChatPhase.DISCOVERY, ChatPhase.CONTEXT},
                )
                if not turn.tool_calls:
                    break
                rounds += 1
                if rounds > MAX_TOOL_ROUNDS:
                    if core_data_emitted:
                        yield _replan_warning()
                        break
                    raise AppError("tool_budget_exhausted", "Tool planning limit reached", 503)

                yield ChatEvent(
                    type=ChatEventType.STATUS,
                    payload={
                        "stage": "fetching_data",
                        "phase": phase.value,
                        "completed": 0,
                        "total": len(turn.tool_calls),
                    },
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
                outcomes = await executor.execute(
                    turn.tool_calls,
                    allowed_names={item["function"]["name"] for item in catalog},
                    known_match_ids=known_match_ids,
                )
                rejected_count = 0
                received_data = False
                batch_has_core_data = any(
                    outcome.result is not None
                    and outcome.status
                    in {ToolOutcomeStatus.SUCCESS, ToolOutcomeStatus.PARTIAL}
                    and outcome.requiredness is ToolRequiredness.CORE
                    for outcome in outcomes
                )
                for outcome in outcomes:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": outcome.call_id,
                            "content": json.dumps(
                                _model_tool_outcome(outcome), ensure_ascii=False
                            ),
                        }
                    )
                    if (
                        outcome.result is not None
                        and outcome.status
                        in {ToolOutcomeStatus.SUCCESS, ToolOutcomeStatus.PARTIAL}
                    ):
                        known_match_ids.update(
                            match.id for match in outcome.result.matches
                        )
                        if outcome.duplicate_of is None:
                            verified_facts.append(_model_tool_result(outcome.result))
                            yield ChatEvent(
                                type=ChatEventType.DATA,
                                payload=outcome.result.model_dump(mode="json"),
                            )
                        data_emitted = True
                        received_data = True
                        if outcome.requiredness is ToolRequiredness.CORE:
                            core_data_emitted = True
                            has_discovered_matches = has_discovered_matches or bool(
                                outcome.result.matches
                            )
                    elif outcome.status is ToolOutcomeStatus.REJECTED:
                        rejected_count += 1
                        if outcome.requiredness is ToolRequiredness.OPTIONAL:
                            yield _optional_warning(outcome)
                    elif (
                        outcome.requiredness is ToolRequiredness.CORE
                        and outcome.status
                        in {
                            ToolOutcomeStatus.UNAVAILABLE,
                            ToolOutcomeStatus.FAILED,
                        }
                        and not core_data_emitted
                        and not batch_has_core_data
                    ):
                        raise AppError(
                            outcome.code or "tool_failed",
                            "Tool execution failed",
                            503,
                        )
                    elif outcome.requiredness is ToolRequiredness.OPTIONAL and outcome.status in {
                        ToolOutcomeStatus.UNAVAILABLE,
                        ToolOutcomeStatus.FAILED,
                    }:
                        yield _optional_warning(outcome)
                if rejected_count:
                    replan_count += 1
                    if replan_count > MAX_REPLANS:
                        if core_data_emitted:
                            yield _replan_warning()
                            break
                        raise AppError(
                            "tool_replan_exhausted",
                            "Tool planning could not find a valid request",
                            503,
                        )
                if received_data and (
                    request.scope is ChatScope.GLOBAL
                    or (_requests_match_history(last_user) and request.scope is ChatScope.MATCH)
                ):
                    phase = ChatPhase.ENRICHMENT
                yield ChatEvent(
                    type=ChatEventType.STATUS,
                    payload={
                        "stage": "planning",
                        "phase": phase.value,
                        "completed": len(outcomes),
                        "total": len(turn.tool_calls),
                    },
                )
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
            yield ChatEvent(
                type=ChatEventType.STATUS,
                payload={"stage": "generating", "phase": "synthesis"},
            )
            generated_text = False
            async for chunk in self._model.stream_text(
                _synthesis_messages(messages, verified_facts)
            ):
                generated_text = generated_text or bool(chunk)
                yield ChatEvent(type=ChatEventType.TEXT_DELTA, payload={"delta": chunk})
            if not generated_text:
                yield ChatEvent(
                    type=ChatEventType.TEXT_DELTA,
                    payload={"delta": LLM_FALLBACK_REPLY if data_emitted else LLM_EMPTY_REPLY},
                )
                yield _empty_generation_warning()
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
