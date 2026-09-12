import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.client import FakeChatModel
from app.chat.models import (
    ChatContext,
    ChatEvent,
    ChatEventType,
    ChatMessage,
    ChatRequest,
    ModelTurn,
    StructuredToolResult,
    ToolCall,
)
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


class RecordingProvider:
    def __init__(self, inner: FakeTennisProvider) -> None:
        self.inner = inner
        self.calls: Counter[str] = Counter()

    async def search_players(self, query: str):
        self.calls["search_players"] += 1
        return await self.inner.search_players(query)

    async def get_live_matches(self, *, player_id=None):
        self.calls["get_live_matches"] += 1
        return await self.inner.get_live_matches(player_id=player_id)

    async def get_fixtures(self, *, player_id=None):
        self.calls["get_fixtures"] += 1
        return await self.inner.get_fixtures(player_id=player_id)

    async def get_match(self, match_id: str):
        self.calls["get_match"] += 1
        return await self.inner.get_match(match_id)

    async def get_match_snapshot(self, match_id: str):
        self.calls["get_match_snapshot"] += 1
        return await self.inner.get_match_snapshot(match_id)

    async def get_recent_results(self, player_id: str, *, limit: int):
        self.calls["get_recent_results"] += 1
        return await self.inner.get_recent_results(player_id, limit=limit)

    async def get_head_to_head(self, first_player_id: str, second_player_id: str, *, limit: int):
        self.calls["get_head_to_head"] += 1
        return await self.inner.get_head_to_head(first_player_id, second_player_id, limit=limit)

    async def get_score(self, match_id: str):
        self.calls["get_score"] += 1
        return await self.inner.get_score(match_id)


class WideRecordingProvider(RecordingProvider):
    async def get_live_matches(self, *, player_id=None):
        matches = await super().get_live_matches(player_id=player_id)
        return matches * 30


class CatalogRecordingModel(FakeChatModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.catalog_calls: list[list[str]] = []
        self.stream_catalog_calls: list[list[str]] = []

    async def choose(self, messages, tools, *, parallel_tool_calls=False):
        self.catalog_calls.append(
            [item["function"]["name"] for item in tools]
        )
        return await super().choose(
            messages,
            tools,
            parallel_tool_calls=parallel_tool_calls,
        )

    async def stream_text(self, messages, *, tools=None):
        self.stream_catalog_calls.append(
            [item["function"]["name"] for item in (tools or [])]
        )
        async for chunk in super().stream_text(messages, tools=tools):
            yield chunk


class ConcurrentBusinessTools:
    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.executed: list[str] = []

    def catalog(self, **kwargs):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": name,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
            for name in ("find_player_matches", "get_live_matches")
        ]

    async def freeze_match_context(self, context: ChatContext) -> ChatContext:
        return context

    async def execute(
        self, name: str, arguments: dict, context: ChatContext
    ) -> StructuredToolResult:
        self.executed.append(name)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            return StructuredToolResult(kind="matches")
        finally:
            self.in_flight -= 1


def build_orchestrator(model: FakeChatModel, provider_type=RecordingProvider):
    fake = FakeTennisProvider(identities=MemoryIdentityRepository(), now=lambda: NOW)
    recording = provider_type(fake)
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(recording, cache, now=lambda: NOW, timezone="Asia/Macau")
    tools = BusinessTools(service)
    return ChatOrchestrator(tools, model), recording


def tool_turn(name: str, arguments: dict, call_id: str = "call_1") -> ModelTurn:
    return ModelTurn(tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)])


def global_request(content: str) -> ChatRequest:
    return ChatRequest(scope="global", messages=[ChatMessage(role="user", content=content)])


@pytest.mark.asyncio
async def test_tool_result_precedes_generated_text() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("find_player_matches", {"player_name": "Sinner", "time_scope": "tonight"}),
            ModelTurn(),
        ],
        text_chunks=["Sinner 今晚出场。"],
    )
    orchestrator, _ = build_orchestrator(model)
    request = global_request("今晚 Sinner 几点打？")

    events = [event async for event in orchestrator.stream(request)]

    assert [event.type for event in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "text_delta",
        "done",
    ]
    data = next(event for event in events if event.type is ChatEventType.DATA)
    text = next(event for event in events if event.type is ChatEventType.TEXT_DELTA)
    assert data.payload["matches"][0]["id"].startswith("mat_")
    assert text.payload["delta"] == "Sinner 今晚出场。"
    assert events[-1].payload == {"ok": True}


@pytest.mark.asyncio
async def test_stream_emits_progress_stages_around_planning_and_generation() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("find_player_matches", {"player_name": "Sinner", "time_scope": "tonight"}),
            ModelTurn(),
        ],
        text_chunks=["已完成。"],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("今晚 Sinner 几点打？"))]

    assert [event.payload["stage"] for event in events if event.type is ChatEventType.STATUS] == [
        "resolving",
        "planning",
        "fetching_data",
        "planning",
        "generating",
    ]


@pytest.mark.asyncio
async def test_bounded_model_context_keeps_full_sse_data() -> None:
    model = FakeChatModel(
        turns=[tool_turn("get_live_matches", {}), ModelTurn()],
        text_chunks=["当前有很多场比赛。"],
    )
    orchestrator, _ = build_orchestrator(model, WideRecordingProvider)

    events = [event async for event in orchestrator.stream(global_request("现在有什么比赛？"))]

    data = next(event for event in events if event.type == ChatEventType.DATA)
    assert len(data.payload["matches"]) == 30

    tool_message = next(message for message in model.choose_calls[-1] if message["role"] == "tool")
    model_result = json.loads(tool_message["content"])
    assert len(model_result["matches"]) <= 12
    assert model_result["match_count"] == 30
    assert model_result["truncated"] is True
    assert "freshness" not in model_result["matches"][0]


@pytest.mark.asyncio
async def test_independent_tool_calls_execute_in_parallel() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(
                tool_calls=[
                    ToolCall(
                        id="call_a",
                        name="find_player_matches",
                        arguments={"player_name": "Sinner", "time_scope": "tonight"},
                    ),
                    ToolCall(id="call_b", name="get_live_matches", arguments={}),
                ]
            ),
            ModelTurn(),
        ],
        text_chunks=["已完成。"],
    )
    tools = ConcurrentBusinessTools()

    events = [
        event
        async for event in ChatOrchestrator(tools, model).stream(
            global_request("今晚和现在的比赛？")
        )
    ]

    assert tools.max_in_flight == 2
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_duplicate_tool_call_reuses_the_first_result() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_live_matches", {}, "call_1"),
            tool_turn("get_live_matches", {}, "call_2"),
            ModelTurn(),
        ],
        text_chunks=["已完成。"],
    )
    tools = ConcurrentBusinessTools()

    events = [
        event
        async for event in ChatOrchestrator(tools, model).stream(
            global_request("现在有什么比赛？")
        )
    ]

    assert tools.executed.count("get_live_matches") == 1
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_invalid_global_match_tool_is_rejected_without_execution() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_match", {}, "call_invalid"),
            ModelTurn(),
        ],
        text_chunks=["没有足够的比赛 ID。"],
    )
    orchestrator, recording = build_orchestrator(model)

    events = [
        event
        async for event in orchestrator.stream(global_request("查一下比赛详情"))
    ]

    assert recording.calls["get_match"] == 0
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_llm_failure_after_data_keeps_structured_result() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_live_matches", {}),
            ModelTurn(),
        ],
        stream_error=RuntimeError("stream boom"),
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("现在有什么比赛？"))]

    assert [event.type for event in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "text_delta",
        "error",
    ]
    text = next(event for event in events if event.type is ChatEventType.TEXT_DELTA)
    assert text.payload["delta"] == "比赛数据已找到，但 AI 说明暂时不可用。"
    assert events[-1].payload["code"] == "llm_unavailable"


@pytest.mark.asyncio
async def test_broad_historical_query_emits_unsupported_without_model_or_provider() -> None:
    model = FakeChatModel()
    orchestrator, recording = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("Sinner 的全部历史战绩"))]

    assert [event.type for event in events] == ["data", "text_delta", "done"]
    assert events[0].payload["kind"] == "unsupported"
    assert events[0].payload["matches"] == []
    assert events[1].payload["delta"] == "P2 暂不支持大范围历史查询。"
    assert model.choose_calls == []
    assert sum(recording.calls.values()) == 0


@pytest.mark.asyncio
async def test_supported_yesterday_query_uses_history_tool() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn(
                "get_player_results",
                {"player_name": "Sinner", "scope": "yesterday", "limit": 5},
            ),
            ModelTurn(),
        ],
        text_chunks=["供应商当前未返回昨天的比赛。"],
    )
    orchestrator, recording = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("昨天 Sinner 赢了吗？"))]

    assert [event.type for event in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "text_delta",
        "done",
    ]
    data = next(event for event in events if event.type is ChatEventType.DATA)
    assert data.payload["kind"] == "matches"
    assert data.payload["metadata"]["scope"] == "yesterday"
    assert recording.calls["get_recent_results"] == 1


@pytest.mark.asyncio
async def test_provider_exception_emits_only_status_and_error() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("find_player_matches", {"player_name": "Federer", "time_scope": "next"}),
        ],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("Federer 下一场对谁？"))]

    assert [event.type for event in events] == ["status", "status", "status", "error"]
    assert events[-1].payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_third_tool_round_is_rejected() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_live_matches", {}, "call_1"),
            tool_turn("get_live_matches", {}, "call_2"),
            tool_turn("get_live_matches", {}, "call_3"),
        ],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("现在有什么比赛？"))]

    assert [event.type for event in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "status",
        "error",
    ]
    assert events[-1].payload["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_match_scope_context_appears_in_system_message() -> None:
    model = FakeChatModel(
        turns=[tool_turn("get_match", {}), ModelTurn()],
        text_chunks=["本场比赛数据已就绪。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    known_match_id = recording.inner.live_match.id
    request = ChatRequest(
        scope="match",
        match_id=known_match_id,
        messages=[ChatMessage(role="user", content="谁在发球？")],
    )

    events = [event async for event in orchestrator.stream(request)]

    assert [event.type for event in events] == [
        "status",
        "status",
        "status",
        "data",
        "status",
        "status",
        "text_delta",
        "done",
    ]
    data = next(event for event in events if event.type is ChatEventType.DATA)
    assert data.payload["kind"] == "match"
    assert data.payload["matches"][0]["id"] == known_match_id
    assert data.payload["answer_context"]["match_id"] == known_match_id

    system_message = model.choose_calls[0][0]
    assert system_message["role"] == "system"
    assert known_match_id in system_message["content"]


@pytest.mark.asyncio
async def test_match_scope_freezes_one_snapshot_for_all_context_tools() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(
                tool_calls=[
                    ToolCall(id="call_match", name="get_match", arguments={}),
                    ToolCall(
                        id="call_score",
                        name="get_match_intelligence",
                        arguments={"topic": "score"},
                    ),
                ]
            ),
            ModelTurn(),
        ],
        text_chunks=["回答基于同一份比赛快照。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    request = ChatRequest(
        scope="match",
        match_id=match_id,
        messages=[ChatMessage(role="user", content="当前比分和本场比赛信息？")],
    )
    events = [event async for event in orchestrator.stream(request)]

    data_events = [event for event in events if event.type is ChatEventType.DATA]
    assert [event.type for event in events] == [
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.DATA,
        ChatEventType.DATA,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.TEXT_DELTA,
        ChatEventType.DONE,
    ]
    assert recording.calls["get_match_snapshot"] == 1
    assert recording.calls["get_match"] == 0
    assert [event.payload["answer_context"] for event in data_events] == [
        data_events[0].payload["answer_context"],
        data_events[0].payload["answer_context"],
    ]


@pytest.mark.asyncio
async def test_match_current_analysis_does_not_offer_unrequested_history_tools() -> None:
    model = CatalogRecordingModel(turns=[ModelTurn()], text_chunks=["已完成。"])
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    request = ChatRequest(
        scope="match",
        match_id=match_id,
        messages=[
            ChatMessage(
                role="user",
                content="分析当前比赛的每盘统计、趋势和原因。",
            )
        ],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert [event.type for event in events] == [
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.TEXT_DELTA,
        ChatEventType.DONE,
    ]
    assert model.catalog_calls == [["get_match_intelligence"]]
    assert model.stream_catalog_calls == [[]]


@pytest.mark.asyncio
async def test_match_scope_optional_player_lookup_does_not_abort_existing_answer() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn(
                "get_match_intelligence",
                {"topic": "statistics"},
                "call_statistics",
            ),
            tool_turn(
                "get_player_results",
                {"player_name": "Unknown Player", "scope": "recent", "limit": 5},
                "call_player_results",
            ),
            ModelTurn(),
        ],
        text_chunks=["已基于提问时快照完成分析；球员背景资料暂未提供。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    request = ChatRequest(
        scope="match",
        match_id=match_id,
        messages=[ChatMessage(role="user", content="分析当前比赛和球员特点。")],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert [event.type for event in events] == [
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.DATA,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.STATUS,
        ChatEventType.TEXT_DELTA,
        ChatEventType.DONE,
    ]
    assert events[-2].payload["delta"].endswith("暂未提供。")
    last_choose = model.choose_calls[-1]
    unavailable_tool = next(
        message
        for message in last_choose
        if message.get("role") == "tool"
        and "call_player_results" == message.get("tool_call_id")
    )
    assert json.loads(unavailable_tool["content"]) == {
        "kind": "unavailable",
        "tool": "get_player_results",
        "code": "not_found",
    }


@pytest.mark.asyncio
async def test_match_intelligence_data_carries_immutable_answer_context() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_match_intelligence", {"topic": "momentum"}),
            ModelTurn(),
        ],
        text_chunks=["当前走势数据暂不可用。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    request = ChatRequest(
        scope="match",
        match_id=match_id,
        messages=[ChatMessage(role="user", content="最近走势如何？")],
    )
    events = [event async for event in orchestrator.stream(request)]

    data = next(event for event in events if event.type is ChatEventType.DATA)
    assert data.payload["kind"] == "intelligence"
    assert data.payload["answer_context"] == {
        "match_id": match_id,
        "state_version": data.payload["packet"]["state_version"],
        "as_of": data.payload["packet"]["as_of"],
    }
    assert "event_key" not in json.dumps(data.payload)


@pytest.mark.asyncio
async def test_match_scope_without_match_id_is_invalid() -> None:
    model = FakeChatModel()
    orchestrator, recording = build_orchestrator(model)
    request = ChatRequest(scope="match", messages=[ChatMessage(role="user", content="谁在发球？")])

    events = [event async for event in orchestrator.stream(request)]

    assert [event.type for event in events] == ["error"]
    assert events[0].payload["code"] == "invalid_request"
    assert model.choose_calls == []
    assert sum(recording.calls.values()) == 0


@pytest.mark.asyncio
async def test_choose_failure_without_data_emits_terminal_llm_error() -> None:
    model = FakeChatModel(choose_error=AppError("llm_unavailable", "LLM down", 503))
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("今晚 Sinner 几点打？"))]

    assert [event.type for event in events] == ["status", "status", "error"]
    assert events[-1].payload["code"] == "llm_unavailable"


@pytest.mark.asyncio
async def test_stream_failure_without_data_emits_only_terminal_error() -> None:
    model = FakeChatModel(turns=[ModelTurn()], stream_error=RuntimeError("boom"))
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("你好"))]

    assert [event.type for event in events] == ["status", "status", "status", "error"]
    assert events[-1].payload["code"] == "llm_unavailable"


def test_sse_frame_ends_with_exactly_two_newlines() -> None:
    event = ChatEvent(type=ChatEventType.DATA, payload={"kind": "matches", "matches": []})
    frame = event.to_sse()

    assert frame == 'event: data\ndata: {"kind": "matches", "matches": []}\n\n'
    assert frame.endswith("\n\n")
    assert not frame.endswith("\n\n\n")


def test_sse_frame_keeps_non_ascii_text() -> None:
    event = ChatEvent(type=ChatEventType.TEXT_DELTA, payload={"delta": "你好"})
    assert "你好" in event.to_sse()
    assert json.loads(event.to_sse().split("data: ")[1])["delta"] == "你好"


@pytest.mark.asyncio
async def test_runtime_default_heuristics_drive_fake_model() -> None:
    model = FakeChatModel()
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("今晚 Sinner 几点打？"))]

    types = [event.type for event in events]
    assert types[0] == "status"
    assert "data" in types
    assert types[-1] == "done"
    data = next(event for event in events if event.type == "data")
    assert data.payload["kind"] == "matches"
    assert data.payload["matches"], "heuristic should resolve Sinner tonight via the fake provider"
