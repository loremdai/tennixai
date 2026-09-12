"""Chat orchestrator: historical guard, bounded tool loop, data-first fallback.

Status events expose the phases before and during model work. Structured data
is always emitted before generated prose so the UI can render trusted cards
even when the model later fails.
"""

import json
import re
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
    ModelTurn,
    StructuredToolResult,
    ToolCall,
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
from app.intelligence import IntelligencePacket, IntelligenceTopic

HISTORICAL_REPLY = "P2 暂不支持大范围历史查询。"
LLM_FALLBACK_REPLY = "比赛数据已找到，但 AI 说明暂时不可用。"
LLM_EMPTY_REPLY = "暂时没有生成可展示的回答，请稍后重试。"
UNKNOWN_FORMAT_REPLY = "比赛数据已找到，但本次没有生成可展示的分析。"
UNKNOWN_FORMAT_WARNING = "赛制信息暂缺，以下分析未对具体盘数结构作判断。"
UNKNOWN_FORMAT_TERMS = re.compile(
    r"(?:\bbo\s*[35]\b|\bbest[ -]+of[ -]+(?:three|five|[35])\b|"
    r"三盘两胜|五盘三胜|第\s*(?:5|５|五)\s*盘|第五盘|"
    r"\b3\s*[-–—]\s*1\b)",
    flags=re.IGNORECASE,
)
UNKNOWN_FORMAT_META_SENTENCE = re.compile(
    r"(?:^|(?<=[。！？]))[^。！？]*(?:严格遵守规则|赛制推断术语|质量校验|禁用词清单|校验过程|"
    r"format[^。！？]*(?:null|未返回|未提供|字段)|"
    r"(?:未返回|未提供|缺失)[^。！？]{0,20}(?:赛制|format)|"
    r"(?:无法推断|不推断)[^。！？]*(?:赛制|盘数)|"
    r"未经核验的盘数比分)"
    r"[^。！？]*[。！？]"
)
PLAYER_PROFILE_META_SENTENCE = re.compile(
    r"(?:^|(?<=[。！？]))(?:同时，)?[^。！？]*(?:两位球员|球员)[^。！？]*"
    r"(?:历史特点|优缺点)[^。！？]*(?:暂未提供|不可用|未返回|工具)[^。！？]*[。！？]"
)
IMPORTANT_NOTICE_LABEL = re.compile(
    r"(?m)^\s*(?:\*\*|__)?重要(?:说明|提示)[:：](?:\*\*|__)?\s*"
)
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
    "统计结果中的 player_values 已明确标注球员姓名，必须按姓名读取，不能交换两列。"
    "如果字段为 null、空数组或质量状态为 unavailable，必须明确标注暂不可用；不得从赛事名称、轮次、网球常识或当前比分推断未返回的赛制、场地属性、统计、逐分数据或球员事实。"
    "特别是 format 未返回时，禁止写 BO3、BO5、三盘两胜、五盘三胜、第五盘或任何基于未知赛制的最终盘数比分；预测只说明胜者倾向和依据。"
    "趋势和控制指数只能做描述性分析，不得编造赔率、概率或确定性的胜负结论。"
    "工具返回 kind=player_resolution 时：status 为 ambiguous 表示多名候选，"
    "必须用自然语言列出候选（英文名、中文名、国家、排名）并请用户选择，不得自行猜测；"
    "status 为 not_found 表示目录未命中，请用户补充英文或中文全名、国家或赛事；"
    "两者都是正常业务结果，直接据此组织回答并正常结束，不得输出系统错误话术。"
    "已解析球员同时有英文名和中文名时，第一次提及使用“英文名（中文名）”格式，之后可只用英文全名或姓氏。"
)
MATCH_SYSTEM_SUFFIX = (
    "当前比赛已由页面上下文确定（current match id: {match_id}），"
    "本次问答以提问开始时冻结的同一份比赛快照为事实基线；所有上下文事实问题先调用 get_match_intelligence，"
    "综合问题可按需调用 overview、score、statistics、points、momentum，调用 get_match 时无需提供参数，"
    "如果问题要求每盘技术统计、逐分趋势、原因或胜负预测，必须综合已返回的 overview、statistics、points、momentum；"
    "某一主题为空时只说明该主题不可用，不得用推测补齐；统计必须以球员姓名对应的值为准。"
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

MATCH_COMPREHENSIVE_PHRASES = (
    "技术统计",
    "每盘",
    "每一盘",
    "逐分",
    "关键分",
    "趋势",
    "走势",
    "动量",
    "控制指数",
    "momentum",
    "statistics",
    "详细分析",
    "详细信息",
    "预测",
    "谁能获胜",
    "谁会赢",
)


def _requests_match_history(text: str) -> bool:
    normalized = text.casefold()
    return is_historical_query(text) or any(
        phrase in normalized for phrase in MATCH_HISTORY_PHRASES
    )


def _requested_match_topics(text: str) -> tuple[IntelligenceTopic, ...]:
    """Return deterministic context coverage for questions that need synthesis."""
    normalized = text.casefold()
    if not any(phrase in normalized for phrase in MATCH_COMPREHENSIVE_PHRASES):
        return ()
    return (
        IntelligenceTopic.OVERVIEW,
        IntelligenceTopic.STATISTICS,
        IntelligenceTopic.POINTS,
        IntelligenceTopic.MOMENTUM,
    )


def _has_unknown_format(snapshot: Any, facts: list[dict[str, Any]]) -> bool:
    if snapshot is not None and snapshot.match.format is None:
        return True
    for fact in facts:
        packet = fact.get("packet")
        if isinstance(packet, dict) and packet.get("format") is None:
            return True
        for match in fact.get("matches", []):
            if isinstance(match, dict) and match.get("format") is None:
                return True
    return False


def _contains_unknown_format_term(text: str) -> bool:
    return bool(UNKNOWN_FORMAT_TERMS.search(text))


def _replace_unknown_format_term(match: re.Match[str]) -> str:
    term = match.group(0)
    if re.search(r"\b3\s*[-–—]\s*1\b", term):
        return "未核验的盘数比分"
    if "盘" in term:
        return "后续盘次"
    return "具体赛制"


def _sanitize_unknown_format_response(text: str) -> str:
    sanitized = UNKNOWN_FORMAT_TERMS.sub(_replace_unknown_format_term, text).strip()
    sanitized = UNKNOWN_FORMAT_META_SENTENCE.sub("", sanitized).strip()
    sanitized = PLAYER_PROFILE_META_SENTENCE.sub(
        "以下分析主要依据本场比赛已记录的比分和技术统计。",
        sanitized,
    ).strip()
    sanitized = IMPORTANT_NOTICE_LABEL.sub("", sanitized).strip()
    if not sanitized:
        return UNKNOWN_FORMAT_REPLY
    return sanitized


def _planned_match_context_calls(
    required_topics: tuple[IntelligenceTopic, ...],
    completed_topics: set[IntelligenceTopic],
    calls: list[ToolCall],
) -> list[ToolCall]:
    selected_topics = {
        call.arguments.get("topic")
        for call in calls
        if call.name == "get_match_intelligence"
    }
    planned: list[ToolCall] = []
    for topic in required_topics:
        if topic in completed_topics or topic.value in selected_topics:
            continue
        planned.append(
            ToolCall(
                id=f"planned_context_{topic.value}",
                name="get_match_intelligence",
                arguments={"topic": topic.value},
            )
        )
    return planned


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


def _model_intelligence_packet(packet: IntelligencePacket) -> dict[str, Any]:
    payload = packet.model_dump(mode="json")
    players = packet.players
    for statistic in payload["statistics"]:
        statistic["player_values"] = [
            {"player": players[0], "value": statistic["player1_value"]},
            {"player": players[1], "value": statistic["player2_value"]},
        ]
    if packet.score is not None:
        payload["score_by_player"] = [
            {
                "player": players[index],
                "sets_won": packet.score.sets_won[index],
                "sets": [
                    {
                        "number": set_score.number,
                        "games": (
                            set_score.player1_games
                            if index == 0
                            else set_score.player2_games
                        ),
                    }
                    for set_score in packet.score.sets
                ],
                "current_point": packet.score.points[index],
            }
            for index in range(2)
        ]
    return payload


def _model_player_display(player, *, rank: int | None = None) -> dict[str, Any]:
    """Public candidate fields only; bilingual display name for first mention."""
    display = (
        f"{player.name}（{player.localized_name}）"
        if player.localized_name
        else player.name
    )
    return {
        "id": player.id,
        "display_name": display,
        "name": player.name,
        "localized_name": player.localized_name,
        "country_code": player.country_code,
        "ranking": rank if rank is not None else player.ranking,
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
        payload["packet"] = _model_intelligence_packet(result.packet)
    if result.resolution is not None:
        resolution = result.resolution
        payload["resolution"] = {
            "status": resolution.status.value,
            "query": resolution.query,
            "player": (
                _model_player_display(resolution.player)
                if resolution.player is not None
                else None
            ),
            "candidates": [
                _model_player_display(candidate.player, rank=candidate.current_rank)
                for candidate in resolution.candidates
            ],
        }
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
                "只能根据这些事实回答，缺失字段请明确说明。统计值必须按 player_values 中的球员姓名读取，"
                "不要复述本提示、内部规则、质量校验、禁用词清单或生成过程，不要写‘严格遵守规则’等元话术，"
                "不要使用‘重要说明’‘重要提示’等模板标题，直接开始回答。"
                "不要在正文提及工具、format 字段、赛制字段缺失或无法推断盘数等实现细节；这类资料提示由页面单独展示。"
                "若历史特征资料未提供，用自然中文简短说明资料不足，不要描述工具调用或内部字段。"
                "直接给出原问题需要的事实、分析和结论。若 status 为 finished 且 winner_player 有值，"
                "明确这是已发生的比赛结果，不要把它称为预测。"
                "不能交换两列。若任何事实中的 format 为 null，整篇回答严禁出现 BO3、BO5、三盘两胜、"
                "五盘三胜、第五盘或最终盘数比分（例如 3-1）；只能预测胜者倾向，不得补猜赛制：\n"
                f"{json.dumps(verified_facts, ensure_ascii=False)}"
            ),
        }
    )
    return clean_messages


def _response_sanitized_warning() -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "llm_response_sanitized",
            "message": "AI 回答已按提问时冻结的事实完成安全校验。",
            "details": {},
        },
    )


def _unknown_format_warning() -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "match_format_unavailable",
            "message": UNKNOWN_FORMAT_WARNING,
            "details": {},
        },
    )


def _generation_unavailable_warning() -> ChatEvent:
    return ChatEvent(
        type=ChatEventType.WARNING,
        payload={
            "code": "llm_response_unavailable",
            "message": "AI 说明生成失败，已保留结构化比赛数据并完成本次查询。",
            "details": {},
        },
    )


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
            "code": "llm_response_empty",
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
        required_topics = _requested_match_topics(last_user)
        completed_topics: set[IntelligenceTopic] = set()

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
                if request.scope is ChatScope.MATCH and phase is ChatPhase.CONTEXT:
                    turn = turn.model_copy(
                        update={
                            "tool_calls": [
                                *turn.tool_calls,
                                *_planned_match_context_calls(
                                    required_topics,
                                    completed_topics,
                                    turn.tool_calls,
                                ),
                            ]
                        }
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
                        if (
                            outcome.result.packet is not None
                            and outcome.result.kind == "intelligence"
                        ):
                            completed_topics.add(outcome.result.packet.topic)
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
                if (
                    request.scope is ChatScope.MATCH
                    and phase is ChatPhase.CONTEXT
                    and received_data
                    and (
                        not required_topics
                        or set(required_topics) <= completed_topics
                    )
                ):
                    break
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
            synthesis_messages = _synthesis_messages(messages, verified_facts)
            if _has_unknown_format(context.snapshot, verified_facts):
                raw_generated = ""
                async for chunk in self._model.stream_text(synthesis_messages):
                    raw_generated += chunk
                had_forbidden_term = _contains_unknown_format_term(raw_generated)
                generated = _sanitize_unknown_format_response(raw_generated)
                if had_forbidden_term:
                    yield _response_sanitized_warning()
                if generated.strip():
                    yield ChatEvent(
                        type=ChatEventType.TEXT_DELTA,
                        payload={"delta": generated},
                    )
                else:
                    yield ChatEvent(
                        type=ChatEventType.TEXT_DELTA,
                        payload={
                            "delta": (
                                UNKNOWN_FORMAT_REPLY
                                if data_emitted
                                else LLM_EMPTY_REPLY
                            )
                        },
                    )
                    yield _empty_generation_warning()
                yield _unknown_format_warning()
            else:
                generated_text = False
                async for chunk in self._model.stream_text(synthesis_messages):
                    generated_text = generated_text or bool(chunk.strip())
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
                yield _generation_unavailable_warning()
                yield ChatEvent(type=ChatEventType.DONE, payload={"ok": True})
                return
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
