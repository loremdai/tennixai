import asyncio
import json
from collections import Counter
from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.client import FakeChatModel
from app.chat.executor import ToolBatchExecutor
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
from app.domain import Player
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


class MixedOutcomeBusinessTools(ConcurrentBusinessTools):
    async def execute(
        self, name: str, arguments: dict, context: ChatContext
    ) -> StructuredToolResult:
        if name == "find_player_matches":
            self.executed.append(name)
            raise AppError("not_found", "Player not found", 404)
        return await super().execute(name, arguments, context)


class UnknownFormatRecordingProvider(RecordingProvider):
    async def get_match_snapshot(self, match_id: str):
        snapshot = await super().get_match_snapshot(match_id)
        return snapshot.model_copy(
            update={
                "match": snapshot.match.model_copy(update={"format": None}),
            }
        )


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
async def test_duplicate_tool_calls_in_one_batch_execute_once() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(
                tool_calls=[
                    ToolCall(id="call_1", name="get_live_matches", arguments={}),
                    ToolCall(id="call_2", name="get_live_matches", arguments={}),
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
            global_request("现在有什么比赛？")
        )
    ]

    assert tools.executed.count("get_live_matches") == 1
    tool_messages = [message for message in model.choose_calls[-1] if message["role"] == "tool"]
    assert len(tool_messages) == 2
    assert json.loads(tool_messages[0]["content"]) == json.loads(tool_messages[1]["content"])
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_mixed_batch_keeps_independent_calls_parallel() -> None:
    tools = ConcurrentBusinessTools()
    executor = ToolBatchExecutor(tools, ChatContext(scope="global"))
    calls = [
        ToolCall(id="call_match", name="get_match", arguments={"match_id": "mat_known"}),
        ToolCall(id="call_live", name="get_live_matches", arguments={}),
        ToolCall(
            id="call_player",
            name="find_player_matches",
            arguments={"player_name": "Sinner", "time_scope": "tonight"},
        ),
    ]

    outcomes = await executor.execute(
        calls,
        allowed_names={"get_match", "get_live_matches", "find_player_matches"},
        known_match_ids={"mat_known"},
    )

    assert tools.max_in_flight == 2
    assert [outcome.call_id for outcome in outcomes] == [
        "call_match",
        "call_live",
        "call_player",
    ]


@pytest.mark.asyncio
async def test_core_batch_success_survives_another_core_call_failure() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(
                tool_calls=[
                    ToolCall(
                        id="call_missing",
                        name="find_player_matches",
                        arguments={"player_name": "Unknown", "time_scope": "tonight"},
                    ),
                    ToolCall(id="call_live", name="get_live_matches", arguments={}),
                ]
            ),
            ModelTurn(),
        ],
        text_chunks=["已使用可用比赛数据完成回答。"],
    )
    tools = MixedOutcomeBusinessTools()

    events = [
        event
        async for event in ChatOrchestrator(tools, model).stream(
            global_request("Unknown 和现在的比赛？")
        )
    ]

    assert any(event.type is ChatEventType.DATA for event in events)
    assert not any(event.type is ChatEventType.ERROR for event in events)
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
async def test_global_illegal_match_tool_replans_without_invalid_request() -> None:
    model = CatalogRecordingModel(
        turns=[
            tool_turn(
                "find_player_matches",
                {"player_name": "Sinner", "time_scope": "tonight"},
                "call_find",
            ),
            tool_turn(
                "get_match_intelligence",
                {"topic": "overview"},
                "call_illegal",
            ),
            ModelTurn(),
        ],
        text_chunks=["已找到 Sinner 的比赛。"],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [
        event
        async for event in orchestrator.stream(
            global_request("Sinner 的比赛如何了")
        )
    ]

    assert any(event.type is ChatEventType.DATA for event in events)
    assert events[-1].type is ChatEventType.DONE
    assert not any(
        event.type is ChatEventType.ERROR
        and event.payload.get("code") == "invalid_request"
        for event in events
    )
    rejected = next(
        message
        for message in model.choose_calls[-1]
        if message.get("tool_call_id") == "call_illegal"
    )
    assert json.loads(rejected["content"])["kind"] == "rejected"


@pytest.mark.asyncio
async def test_status_events_include_phase_and_batch_progress() -> None:
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
    orchestrator, _ = build_orchestrator(model)

    events = [
        event
        async for event in orchestrator.stream(
            global_request("今晚和现在的比赛？")
        )
    ]
    statuses = [event for event in events if event.type is ChatEventType.STATUS]

    assert all("phase" in event.payload for event in statuses)
    fetching = next(event for event in statuses if event.payload["stage"] == "fetching_data")
    assert fetching.payload["completed"] == 0
    assert fetching.payload["total"] == 2


@pytest.mark.asyncio
async def test_optional_failure_emits_warning_and_still_completes() -> None:
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
        text_chunks=["已完成当前比赛分析。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[ChatMessage(role="user", content="分析当前比赛和球员特点。")],
            )
        )
    ]

    data_events = [event for event in events if event.type == ChatEventType.DATA]
    resolution_data = next(
        event for event in data_events
        if event.payload.get("kind") == "player_resolution"
    )
    assert resolution_data.payload["resolution"]["status"] == "not_found"
    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_three_planning_rounds_are_allowed_with_a_bounded_loop() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_live_matches", {}, "call_1"),
            tool_turn("get_live_matches", {}, "call_2"),
            tool_turn("get_live_matches", {}, "call_3"),
            ModelTurn(),
        ],
        text_chunks=["已完成。"],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [
        event
        async for event in orchestrator.stream(global_request("现在有什么比赛？"))
    ]

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
        "warning",
        "done",
    ]
    text = next(event for event in events if event.type is ChatEventType.TEXT_DELTA)
    assert text.payload["delta"] == "比赛数据已找到，但 AI 说明暂时不可用。"
    warning = next(event for event in events if event.type is ChatEventType.WARNING)
    assert warning.payload["code"] == "llm_response_unavailable"
    assert events[-1].type is ChatEventType.DONE


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
            ModelTurn(),
        ],
        text_chunks=["未找到该球员，请补充英文或中文全名、国家或赛事。"],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("Federer 下一场对谁？"))]

    data_events = [event for event in events if event.type == ChatEventType.DATA]
    assert data_events[0].payload["kind"] == "player_resolution"
    assert data_events[0].payload["resolution"]["status"] == "not_found"
    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_fourth_tool_round_degrades_after_core_data() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_live_matches", {}, "call_1"),
            tool_turn("get_live_matches", {}, "call_2"),
            tool_turn("get_live_matches", {}, "call_3"),
            tool_turn("get_live_matches", {}, "call_4"),
        ],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [event async for event in orchestrator.stream(global_request("现在有什么比赛？"))]

    assert events[-1].type is ChatEventType.DONE
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "tool_replan_exhausted"
        for event in events
    )
    assert not any(event.type is ChatEventType.ERROR for event in events)


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
                content="当前比分是多少？",
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
async def test_match_comprehensive_analysis_plans_all_context_topics_before_synthesis() -> None:
    model = FakeChatModel(
        turns=[ModelTurn()],
        text_chunks=["已根据冻结快照完成逐盘统计、逐分走势和动量分析。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[
                    ChatMessage(
                        role="user",
                        content="根据当前比赛的每盘技术统计详细信息，分析逐分趋势和原因，并预测谁获胜。",
                    )
                ],
            )
        )
    ]

    topics = {
        event.payload["packet"]["topic"]
        for event in events
        if event.type is ChatEventType.DATA
        and event.payload.get("kind") == "intelligence"
    }
    assert {"overview", "statistics", "points", "momentum"} <= topics
    fetching = [
        event
        for event in events
        if event.type is ChatEventType.STATUS
        and event.payload.get("stage") == "fetching_data"
    ]
    assert any(event.payload["total"] >= 4 for event in fetching)
    assert not any(event.type is ChatEventType.ERROR for event in events)
    text = "".join(
        event.payload["delta"]
        for event in events
        if event.type is ChatEventType.TEXT_DELTA
    )
    assert text.strip()
    synthesis_facts = next(
        message["content"]
        for message in model.stream_calls[-1]
        if message.get("role") == "user"
        and "以下是提问时冻结并已核验的事实" in message.get("content", "")
    )
    for topic in ("overview", "statistics", "points", "momentum"):
        assert f'"topic": "{topic}"' in synthesis_facts
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_unknown_format_answer_is_sanitized_before_text_is_emitted() -> None:
    model = FakeChatModel(
        text_chunks=["无法确定本场是否为 BO3，盘数比分可能是 3-1。"],
        turns=[ModelTurn()],
    )
    orchestrator, recording = build_orchestrator(model, UnknownFormatRecordingProvider)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[
                    ChatMessage(
                        role="user",
                        content="根据当前比赛的每盘技术统计详细信息，分析趋势和原因，并预测谁能获胜。",
                    )
                ],
            )
        )
    ]

    text = "".join(
        event.payload["delta"]
        for event in events
        if event.type is ChatEventType.TEXT_DELTA
    )
    assert "无法推断盘数结构" not in text
    assert "BO3" not in text
    assert "3-1" not in text
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "llm_response_sanitized"
        for event in events
    )
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "match_format_unavailable"
        for event in events
    )
    assert len(model.stream_calls) == 1
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_unknown_format_answer_sanitizes_all_forbidden_format_terms() -> None:
    model = FakeChatModel(
        text_chunks=["本场可能是 BO5，接下来是第五盘，盘数比分为 3–1。"],
        turns=[ModelTurn()],
    )
    orchestrator, recording = build_orchestrator(model, UnknownFormatRecordingProvider)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[
                    ChatMessage(
                        role="user",
                        content="根据当前比赛的每盘技术统计详细信息，分析趋势和原因，并预测谁能获胜。",
                    )
                ],
            )
        )
    ]

    text = "".join(
        event.payload["delta"]
        for event in events
        if event.type is ChatEventType.TEXT_DELTA
    )
    assert "BO" not in text
    assert "第五盘" not in text
    assert "3–1" not in text
    assert "无法推断盘数结构" not in text
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "llm_response_sanitized"
        for event in events
    )
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "match_format_unavailable"
        for event in events
    )
    assert len(model.stream_calls) == 1
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_unknown_format_answer_drops_internal_quality_rule_text() -> None:
    model = FakeChatModel(
        text_chunks=[
            "**重要说明：** 本场比赛状态为“finished”（已结束），胜者为 **Ben Shelton**。"
            "因此以下结论为对已发生比赛结果的事实复盘与原因分析，而非预测。"
            "由于工具未返回赛制字段（format 为 null），本文不推断具体赛制盘数。"
            "同时，两位球员的历史特点、优缺点资料暂未提供，以下分析完全基于本场各盘技术统计事实。"
        ],
        turns=[ModelTurn()],
    )
    orchestrator, recording = build_orchestrator(model, UnknownFormatRecordingProvider)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[
                    ChatMessage(
                        role="user",
                        content="根据当前比赛的技术统计分析趋势。",
                    )
                ],
            )
        )
    ]

    text = "".join(
        event.payload["delta"]
        for event in events
        if event.type is ChatEventType.TEXT_DELTA
    )
    assert "重要说明" not in text
    assert "无法推断盘数结构" not in text
    assert "format 字段" not in text
    assert "format 为 null" not in text
    assert "工具未返回赛制字段" not in text
    assert "不推断具体赛制盘数" not in text
    assert "两位球员的历史特点、优缺点资料暂未提供" not in text
    assert "以下分析主要依据本场比赛已记录的比分和技术统计" in text
    assert "历史特点和优缺点资料当前不可用" not in text
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "match_format_unavailable"
        for event in events
    )
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_match_scope_rejects_unrequested_history_tool_calls() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn(
                "get_player_results",
                {"player_name": "Sinner", "scope": "recent", "limit": 5},
                "call_history",
            ),
            ModelTurn(),
        ],
        text_chunks=["已基于当前比赛上下文完成回答。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[ChatMessage(role="user", content="当前比分是多少？")],
            )
        )
    ]

    assert recording.calls["get_recent_results"] == 0
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "optional_data_unavailable"
        for event in events
    )
    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_synthesis_uses_clean_verified_facts_after_replan_exhaustion() -> None:
    model = FakeChatModel(
        turns=[
            tool_turn("get_match_intelligence", {"topic": "overview"}, "call_1"),
            tool_turn("get_match_intelligence", {"topic": "overview"}, "call_2"),
            tool_turn("get_match_intelligence", {"topic": "overview"}, "call_3"),
        ],
        text_chunks=["已基于可用的比赛事实完成回答。"],
    )
    orchestrator, recording = build_orchestrator(model)
    await recording.inner.build()
    match_id = recording.inner.live_match.id

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="match",
                match_id=match_id,
                messages=[
                    ChatMessage(
                        role="user",
                        content="分析当前比赛和球员优缺点。",
                    )
                ],
            )
        )
    ]

    assert events[-1].type is ChatEventType.DONE
    synthesis_messages = model.stream_calls[-1]
    assert not any(message.get("role") == "tool" for message in synthesis_messages)
    assert not any("tool_calls" in message for message in synthesis_messages)
    assert any(
        message.get("role") == "user"
        and "已核验" in str(message.get("content"))
        for message in synthesis_messages
    )


@pytest.mark.asyncio
async def test_empty_synthesis_does_not_silently_complete_after_data() -> None:
    model = FakeChatModel(
        turns=[tool_turn("get_live_matches", {}), ModelTurn()],
        text_chunks=[],
    )
    orchestrator, _ = build_orchestrator(model)

    events = [
        event
        async for event in orchestrator.stream(global_request("现在有什么比赛？"))
    ]

    text = [event for event in events if event.type is ChatEventType.TEXT_DELTA]
    assert text and text[-1].payload["delta"] == "比赛数据已找到，但 AI 说明暂时不可用。"
    assert any(
        event.type is ChatEventType.WARNING
        and event.payload["code"] == "llm_response_empty"
        for event in events
    )
    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE


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

    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE
    data_events = [event for event in events if event.type == ChatEventType.DATA]
    kinds = [event.payload.get("kind") for event in data_events]
    assert "intelligence" in kinds
    assert "player_resolution" in kinds
    last_choose = model.choose_calls[-1]
    resolution_tool = next(
        message
        for message in last_choose
        if message.get("role") == "tool"
        and "call_player_results" == message.get("tool_call_id")
    )
    content = json.loads(resolution_tool["content"])
    assert content["kind"] == "player_resolution"
    assert content["resolution"]["status"] == "not_found"


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


# ---------------------------------------------------------------- T50 resolver


def _resolver_orchestrator(model: FakeChatModel):
    from app.players.models import RankingEntry, RankingMovement, Tour
    from app.players.normalization import derive_english_aliases
    from app.players.repository import MemoryPlayerDirectoryRepository
    from app.players.resolver import PlayerResolver

    fake = FakeTennisProvider(identities=MemoryIdentityRepository(), now=lambda: NOW)
    directory = MemoryPlayerDirectoryRepository()
    wang_a = Player(id="ply_wang_a", name="Xinyu Wang", ranking=25)
    wang_b = Player(id="ply_wang_b", name="Xiyu Wang", ranking=50)
    entries = [
        RankingEntry(player=wang_a, tour=Tour.WTA, rank=25, points=90,
                     movement=RankingMovement.SAME, ranking_date=NOW.date(), fetched_at=NOW),
        RankingEntry(player=wang_b, tour=Tour.WTA, rank=50, points=80,
                     movement=RankingMovement.SAME, ranking_date=NOW.date(), fetched_at=NOW),
    ]
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(
        fake, cache, now=lambda: NOW, timezone="Asia/Macau",
        directory=directory, resolver=PlayerResolver(directory),
    )
    return ChatOrchestrator(BusinessTools(service), model), directory, entries


async def _seed(directory, entries) -> None:
    from app.players.normalization import derive_english_aliases

    await directory.save_ranking_snapshot(tuple(entries))
    for directory_player in await directory.list_players_for_alias_sync(limit=50):
        await directory.upsert_aliases(derive_english_aliases(directory_player))


@pytest.mark.asyncio
async def test_not_found_resolution_ends_done_without_error() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(tool_calls=[ToolCall(
                id="call_1",
                name="find_player_matches",
                arguments={"player_name": "Federer", "time_scope": "next"},
            )]),
            ModelTurn(),
        ],
        text_chunks=["未找到该球员，请补充全名或国家。"],
    )
    orchestrator, directory, entries = _resolver_orchestrator(model)
    await _seed(directory, entries)

    events = [
        event async for event in orchestrator.stream(global_request("Federer 下一场？"))
    ]

    data_events = [e for e in events if e.type is ChatEventType.DATA]
    assert data_events and data_events[0].payload["kind"] == "player_resolution"
    assert data_events[0].payload["resolution"]["status"] == "not_found"
    assert all(e.type is not ChatEventType.ERROR for e in events)
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_ambiguous_resolution_ends_done_with_candidates() -> None:
    model = FakeChatModel(
        turns=[
            ModelTurn(tool_calls=[ToolCall(
                id="call_1",
                name="find_player_matches",
                arguments={"player_name": "Wang", "time_scope": "next"},
            )]),
            ModelTurn(),
        ],
        text_chunks=["有多位 Wang，请选择其中一位。"],
    )
    orchestrator, directory, entries = _resolver_orchestrator(model)
    await _seed(directory, entries)

    events = [
        event async for event in orchestrator.stream(global_request("Wang 下一场？"))
    ]

    data_events = [e for e in events if e.type is ChatEventType.DATA]
    assert data_events and data_events[0].payload["resolution"]["status"] == "ambiguous"
    assert len(data_events[0].payload["resolution"]["candidates"]) == 2
    assert all(e.type is not ChatEventType.ERROR for e in events)
    assert events[-1].type is ChatEventType.DONE
