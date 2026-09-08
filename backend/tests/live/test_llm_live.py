"""Opt-in live LLM gate: real Qwen against deterministic fake tennis data.

Run with: uv run pytest -m llm_live
Requires TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL in the environment.
"""

import os
from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.client import OpenAICompatibleChatModel
from app.chat.models import ChatEventType, ChatMessage, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.domain import DataFreshness, Match, MatchStatus, Tournament
from app.identity import MemoryIdentityRepository
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.llm_live

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


class LiveGateFakeProvider(FakeTennisProvider):
    """Fake provider plus one Djokovic upcoming match, mirroring the acceptance harness."""

    def __init__(self, now) -> None:
        super().__init__(identities=MemoryIdentityRepository(), now=now)
        djokovic = next(player for player in self._players if player.name == "Novak Djokovic")
        ruud = next(player for player in self._players if player.name == "Casper Ruud")
        match = Match(
            id=self._identities.get_or_create("match", "fake", "fake-djokovic-next"),
            status=MatchStatus.SCHEDULED,
            players=(djokovic, ruud),
            tournament=Tournament(
                id=self._identities.get_or_create("tournament", "fake", "fake-atp-finals"),
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


class RecordingBusinessTools(BusinessTools):
    def __init__(self, service: TennisService) -> None:
        super().__init__(service)
        self.executed: list[str] = []

    async def execute(self, name: str, arguments: dict, context):
        self.executed.append(name)
        return await super().execute(name, arguments, context)


def _require_credentials() -> tuple[str, str]:
    api_key = os.environ.get("TENNIX_LLM_API_KEY", "")
    base_url = os.environ.get("TENNIX_LLM_BASE_URL", "")
    if not api_key.strip() or not base_url.strip():
        pytest.skip("TENNIX_LLM_API_KEY / TENNIX_LLM_BASE_URL not configured")
    return api_key, base_url


def _build() -> tuple[ChatOrchestrator, RecordingBusinessTools]:
    api_key, base_url = _require_credentials()
    provider = LiveGateFakeProvider(now=lambda: NOW)
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(provider, cache, now=lambda: NOW, timezone="Asia/Macau")
    tools = RecordingBusinessTools(service)
    model = OpenAICompatibleChatModel(
        api_key=api_key,
        base_url=base_url,
        model=os.environ.get("TENNIX_LLM_MODEL", "qwen3.8-max-0902"),
    )
    return ChatOrchestrator(tools, model), tools


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
    orchestrator, tools = _build()

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
    orchestrator, tools = _build()

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
