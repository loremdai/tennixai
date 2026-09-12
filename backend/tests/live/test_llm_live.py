"""Opt-in live LLM gate: real Qwen against deterministic fake tennis data.

Run with: uv run pytest -m llm_live
Reads TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL from the repository-root .env.
"""

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
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.llm_live

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


class LiveGateFakeProvider(FakeTennisProvider):
    """Fake provider plus one Djokovic upcoming match, mirroring the acceptance harness."""

    def __init__(self, now) -> None:
        super().__init__(identities=MemoryIdentityRepository(), now=now)

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
