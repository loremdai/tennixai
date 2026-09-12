"""Opt-in live LLM gate: real Qwen against deterministic fake tennis data.

Run with: uv run pytest -m llm_live
Reads TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL from the repository-root .env.
"""

import re
from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.client import OpenAICompatibleChatModel
from app.chat.models import ChatEventType, ChatMessage, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.config import Settings
from app.domain import DataFreshness, LiveMatchState, Match, MatchStatus, Player, Tournament
from app.identity import MemoryIdentityRepository
from app.players.models import PlayerAlias, PlayerAliasKind, PlayerAliasSource
from app.players.repository import MemoryPlayerDirectoryRepository
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.llm_live

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


class LiveGateFakeProvider(FakeTennisProvider):
    """Fake provider plus one Djokovic upcoming match, mirroring the acceptance harness."""

    def __init__(self, now) -> None:
        super().__init__(identities=MemoryIdentityRepository(), now=now)
        self.unknown_format_match: Match | None = None

    async def _post_build(self) -> None:
        now = self._now
        djokovic = next(player for player in self._players if player.name == "Novak Djokovic")
        ruud = next(player for player in self._players if player.name == "Casper Ruud")
        match = Match(
            id=await self._identities.get_or_create("match", "fake", "fake-djokovic-next"),
            status=MatchStatus.SCHEDULED,
            players=(djokovic, ruud),
            tournament=Tournament(
                id=await self._identities.get_or_create(
                    "tournament", "fake", "fake-atp-finals"
                ),
                name="ATP Finals",
                tour="atp",
            ),
            scheduled_at=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
            round="Group",
            surface="hard",
            indoor=True,
            format="BO3",
            freshness=DataFreshness(provider="fake", observed_at=now()),
        )
        self._matches[match.id] = match

        tiafoe = Player(
            id=await self._identities.get_or_create("player", "fake", "fake-tiafoe"),
            name="Frances Tiafoe",
            country_code="usa",
            ranking=17,
        )
        self._players.append(tiafoe)
        tiafoe_match = Match(
            id=await self._identities.get_or_create("match", "fake", "fake-tiafoe-next"),
            status=MatchStatus.LIVE,
            players=(tiafoe, ruud),
            tournament=match.tournament,
            scheduled_at=datetime(2026, 9, 8, 10, 30, tzinfo=timezone.utc),
            round="Quarterfinal",
            surface="hard",
            indoor=True,
            format="BO3",
            live_state=LiveMatchState(),
            freshness=DataFreshness(provider="fake", observed_at=now()),
        )
        self._matches[tiafoe_match.id] = tiafoe_match
        self.unknown_format_match = tiafoe_match.model_copy(update={"format": None})
        self._matches[tiafoe_match.id] = self.unknown_format_match


class RecordingBusinessTools(BusinessTools):
    def __init__(self, service: TennisService) -> None:
        super().__init__(service)
        self.executed: list[str] = []

    async def execute(self, name: str, arguments: dict, context):
        self.executed.append(name)
        return await super().execute(name, arguments, context)


def _require_credentials() -> tuple[str, str, str]:
    settings = Settings(provider_mode="fake", llm_mode="fake")
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url
    if api_key is None or not api_key.get_secret_value().strip() or not base_url:
        pytest.skip("TENNIX_LLM_API_KEY / TENNIX_LLM_BASE_URL not configured")
    return api_key.get_secret_value(), base_url, settings.llm_model


def _build() -> tuple[ChatOrchestrator, RecordingBusinessTools, LiveGateFakeProvider]:
    api_key, base_url, model_name = _require_credentials()
    provider = LiveGateFakeProvider(now=lambda: NOW)
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(provider, cache, now=lambda: NOW, timezone="Asia/Macau")
    tools = RecordingBusinessTools(service)
    model = OpenAICompatibleChatModel(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
    )
    return ChatOrchestrator(tools, model), tools, provider


@pytest.mark.parametrize(
    ("question", "expected_tool"),
    [
        ("今晚 Sinner 几点打？", "find_player_matches"),
        ("Alcaraz 今天有比赛吗？", "find_player_matches"),
        ("Djokovic 下一场对谁？", "find_player_matches"),
    ],
)
@pytest.mark.asyncio
async def test_qwen_selects_expected_tool_for_acceptance_prompts(
    question: str, expected_tool: str
) -> None:
    orchestrator, tools, _ = _build()

    request = ChatRequest(
        scope="global",
        messages=[ChatMessage(role="user", content=question)],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert tools.executed and tools.executed[0] == expected_tool
    data = [event.payload for event in events if event.type is ChatEventType.DATA]
    assert data and data[0]["matches"], "tool path must return structured matches"
    text = "".join(
        event.payload["delta"] for event in events if event.type is ChatEventType.TEXT_DELTA
    )
    names = {player["name"] for match in data[0]["matches"] for player in match["players"]}
    assert any(name.split()[-1] in text for name in names) or any(
        token in text for token in ("20:30", "18:00", "12:30")
    ), f"prose should mention a structured opponent or time, got: {text!r}"
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_qwen_selects_get_live_matches_for_live_question() -> None:
    orchestrator, tools, _ = _build()

    request = ChatRequest(
        scope="global",
        messages=[ChatMessage(role="user", content="现在有什么比赛？")],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert tools.executed and tools.executed[0] == "get_live_matches"
    data = [event.payload for event in events if event.type is ChatEventType.DATA]
    assert data and data[0]["matches"]
    live_names = {player["name"] for match in data[0]["matches"] for player in match["players"]}
    text = "".join(
        event.payload["delta"] for event in events if event.type is ChatEventType.TEXT_DELTA
    )
    assert any(name.split()[-1] in text for name in live_names), (
        f"prose should mention a live player, got: {text!r}"
    )
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_qwen_global_question_never_fails_after_structured_data() -> None:
    orchestrator, tools, _ = _build()

    request = ChatRequest(
        scope="global",
        messages=[ChatMessage(role="user", content="tiafoe 的比赛如何了")],
    )
    events = [event async for event in orchestrator.stream(request)]

    data = [event.payload for event in events if event.type is ChatEventType.DATA]
    assert data and data[0]["matches"]
    assert any(
        player["name"] == "Frances Tiafoe"
        for match in data[0]["matches"]
        for player in match["players"]
    )
    assert tools.executed
    assert events[-1].type is ChatEventType.DONE
    assert not any(
        event.type is ChatEventType.ERROR and event.payload.get("code") == "invalid_request"
        for event in events
    )


@pytest.mark.parametrize(
    ("question", "expected_tool"),
    [
        ("昨天 Sinner 赢了吗？", "get_player_results"),
        ("Sinner 和 Alcaraz 的有限交手记录", "get_head_to_head"),
    ],
)
@pytest.mark.asyncio
async def test_qwen_selects_bounded_p2_history_tools(
    question: str, expected_tool: str
) -> None:
    orchestrator, tools, _ = _build()

    request = ChatRequest(
        scope="global",
        messages=[ChatMessage(role="user", content=question)],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert tools.executed and tools.executed[0] == expected_tool
    assert any(event.type is ChatEventType.DATA for event in events)
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_qwen_selects_topic_intelligence_for_match_question() -> None:
    orchestrator, tools, provider = _build()
    await provider.build()
    assert provider.live_match is not None

    request = ChatRequest(
        scope="match",
        match_id=provider.live_match.id,
        messages=[ChatMessage(role="user", content="最近走势如何？")],
    )
    events = [event async for event in orchestrator.stream(request)]

    assert tools.executed and tools.executed[0] == "get_match_intelligence"
    data = next(event.payload for event in events if event.type is ChatEventType.DATA)
    assert data["kind"] == "intelligence"
    assert data["answer_context"]["match_id"] == provider.live_match.id
    assert events[-1].type is ChatEventType.DONE


@pytest.mark.asyncio
async def test_qwen_comprehensive_match_answer_waits_for_all_requested_context() -> None:
    orchestrator, tools, provider = _build()
    await provider.build()
    assert provider.unknown_format_match is not None
    match = provider.unknown_format_match

    request = ChatRequest(
        scope="match",
        match_id=match.id,
        messages=[
            ChatMessage(
                role="user",
                content="根据当前比赛的每盘技术统计详细信息，分析趋势和原因，并大胆预测谁能获胜。",
            )
        ],
    )
    events = [event async for event in orchestrator.stream(request)]

    packets = [
        event.payload["packet"]
        for event in events
        if event.type is ChatEventType.DATA
        and event.payload.get("kind") == "intelligence"
    ]
    assert {packet["topic"] for packet in packets} >= {
        "overview",
        "statistics",
        "points",
        "momentum",
    }
    assert len({
        (packet["match_id"], packet["state_version"], packet["as_of"])
        for packet in packets
    }) == 1
    text = "".join(
        event.payload["delta"]
        for event in events
        if event.type is ChatEventType.TEXT_DELTA
    ).strip()
    assert len(text) >= 40
    player_names = [player.name for player in match.players]
    assert all(
        name in text or name.split()[-1] in text
        for name in player_names
    )
    assert "AI 说明暂时不可用" not in text
    assert not re.search(
        r"(?:BO[35]|三盘两胜|五盘三胜|第\s*5\s*盘|第五盘|\b3-1\b)",
        text,
        flags=re.IGNORECASE,
    )
    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE
    assert tools.executed.count("get_match_intelligence") >= 4


# ---------------------------------------------------------------- T50 resolver


def _build_with_directory() -> tuple[ChatOrchestrator, RecordingBusinessTools, MemoryPlayerDirectoryRepository]:
    from app.players.models import RankingEntry, RankingMovement, Tour
    from app.players.normalization import derive_english_aliases
    from app.players.repository import MemoryPlayerDirectoryRepository
    from app.players.resolver import PlayerResolver

    api_key, base_url, model_name = _require_credentials()
    provider = LiveGateFakeProvider(now=lambda: NOW)
    directory = MemoryPlayerDirectoryRepository()
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(
        provider, cache, now=lambda: NOW, timezone="Asia/Macau",
        directory=directory, resolver=PlayerResolver(directory),
    )
    tools = RecordingBusinessTools(service)
    model = OpenAICompatibleChatModel(api_key=api_key, base_url=base_url, model=model_name)
    return ChatOrchestrator(tools, model), tools, directory


async def _seed_resolver_directory(directory) -> None:
    import asyncio

    from app.players.models import RankingEntry, RankingMovement, Tour
    from app.players.normalization import derive_english_aliases

    entries = [
        RankingEntry(player=Player(id="ply_ben", name="Ben Shelton", ranking=5),
                     tour=Tour.ATP, rank=5, points=5200, movement=RankingMovement.SAME,
                     ranking_date=NOW.date(), fetched_at=NOW),
        RankingEntry(player=Player(id="ply_zheng", name="Qinwen Zheng", ranking=5),
                     tour=Tour.WTA, rank=5, points=5315, movement=RankingMovement.UP,
                     ranking_date=NOW.date(), fetched_at=NOW),
        RankingEntry(player=Player(id="ply_wang_a", name="Xinyu Wang", ranking=25),
                     tour=Tour.WTA, rank=25, points=1800, movement=RankingMovement.UP,
                     ranking_date=NOW.date(), fetched_at=NOW),
        RankingEntry(player=Player(id="ply_wang_b", name="Xiyu Wang", ranking=50),
                     tour=Tour.WTA, rank=50, points=1080, movement=RankingMovement.UP,
                     ranking_date=NOW.date(), fetched_at=NOW),
    ]
    await directory.save_ranking_snapshot(tuple(entries))
    for directory_player in await directory.list_players_for_alias_sync(limit=50):
        await directory.upsert_aliases(derive_english_aliases(directory_player))
    await directory.upsert_aliases(
        (
            PlayerAlias(player_id="ply_ben", locale="zh-Hans", alias="本·谢尔顿",
                        normalized_alias="本谢尔顿", kind=PlayerAliasKind.PREFERRED,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_ben", locale="zh-Hans", alias="谢尔顿",
                        normalized_alias="谢尔顿", kind=PlayerAliasKind.SURNAME,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_zheng", locale="zh-Hans", alias="郑钦文",
                        normalized_alias="郑钦文", kind=PlayerAliasKind.PREFERRED,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_wang_a", locale="zh-Hans", alias="王欣瑜",
                        normalized_alias="王欣瑜", kind=PlayerAliasKind.PREFERRED,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_wang_a", locale="zh-Hans", alias="王",
                        normalized_alias="王", kind=PlayerAliasKind.SURNAME,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_wang_b", locale="zh-Hans", alias="王曦雨",
                        normalized_alias="王曦雨", kind=PlayerAliasKind.PREFERRED,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
            PlayerAlias(player_id="ply_wang_b", locale="zh-Hans", alias="王",
                        normalized_alias="王", kind=PlayerAliasKind.SURNAME,
                        source=PlayerAliasSource.LLM, model="live-gate",
                        prompt_version="zh-Hans-player-name-v1"),
        )
    )


@pytest.mark.parametrize(
    ("question", "requires_data"),
    [
        ("Ben Shelton 下一场什么时候？", True),
        ("Shelton 今天有比赛吗？", True),
        ("谢尔顿现在比分多少？", True),
        # Season records are not a Chat tool yet; an honest "capability
        # unavailable" answer without any tool call is acceptable here.
        ("郑钦文这个赛季战绩如何？", False),
    ],
)
@pytest.mark.asyncio
async def test_qwen_resolves_approved_names_and_ends_done(
    question: str, requires_data: bool
) -> None:
    orchestrator, _tools, directory = _build_with_directory()
    await _seed_resolver_directory(directory)

    events = [
        event
        async for event in orchestrator.stream(
            ChatRequest(
                scope="global",
                messages=[ChatMessage(role="user", content=question)],
            )
        )
    ]

    assert not any(event.type is ChatEventType.ERROR for event in events)
    assert events[-1].type is ChatEventType.DONE
    if requires_data:
        data_events = [event for event in events if event.type is ChatEventType.DATA]
        assert data_events, "expected structured data for a resolved player question"


@pytest.mark.asyncio
async def test_qwen_ambiguous_and_unknown_names_end_done_with_clarification() -> None:
    orchestrator, _tools, directory = _build_with_directory()
    await _seed_resolver_directory(directory)

    for question, expected_status in (
        ("Wang 下一场什么时候？", "ambiguous"),
        ("Zzz Nobody 下一场什么时候？", "not_found"),
    ):
        events = [
            event
            async for event in orchestrator.stream(
                ChatRequest(
                    scope="global",
                    messages=[ChatMessage(role="user", content=question)],
                )
            )
        ]
        assert not any(event.type is ChatEventType.ERROR for event in events)
        assert events[-1].type is ChatEventType.DONE
        resolution_events = [
            event
            for event in events
            if event.type is ChatEventType.DATA
            and event.payload.get("kind") == "player_resolution"
        ]
        assert resolution_events, f"expected resolution data for {question}"
        assert resolution_events[0].payload["resolution"]["status"] == expected_status
