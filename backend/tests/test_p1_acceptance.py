"""P1 acceptance matrix: every supported intent through the real tool loop.

The harness wraps the real ChatOrchestrator with the deterministic fake
provider, a recording BusinessTools, and the FakeChatModel runtime defaults.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.client import FakeChatModel
from app.chat.models import ChatEventType, ChatMessage, ChatRequest
from app.chat.orchestrator import ChatOrchestrator
from app.chat.tools import BusinessTools
from app.domain import (
    DataFreshness,
    Match,
    MatchStatus,
    Tournament,
)
from app.identity import MemoryIdentityRepository
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


class AcceptanceFakeProvider(FakeTennisProvider):
    """FakeTennisProvider plus one Djokovic upcoming match for acceptance coverage."""

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


@dataclass
class AcceptanceResult:
    executed_tool_names: list[str]
    data_events: list[dict]
    terminal_event: str


class CountingProviderWrapper:
    def __init__(self, inner: AcceptanceFakeProvider) -> None:
        self.inner = inner
        self.calls = 0

    async def search_players(self, query: str):
        self.calls += 1
        return await self.inner.search_players(query)

    async def get_live_matches(self, *, player_id=None):
        self.calls += 1
        return await self.inner.get_live_matches(player_id=player_id)

    async def get_fixtures(self, *, player_id=None):
        self.calls += 1
        return await self.inner.get_fixtures(player_id=player_id)

    async def get_match(self, match_id: str):
        self.calls += 1
        return await self.inner.get_match(match_id)

    async def get_score(self, match_id: str):
        self.calls += 1
        return await self.inner.get_score(match_id)


class AcceptanceHarness:
    def __init__(
        self,
        orchestrator: ChatOrchestrator,
        tools: RecordingBusinessTools,
        live_match_id: str,
        provider_calls: CountingProviderWrapper,
        model: FakeChatModel,
    ) -> None:
        self.orchestrator = orchestrator
        self.tools = tools
        self.live_match_id = live_match_id
        self.provider_calls = provider_calls
        self.model = model

    async def ask(self, question: str, scope: str, match_id: str | None) -> AcceptanceResult:
        self.tools.executed.clear()
        request = ChatRequest(
            scope=scope,
            match_id=match_id,
            messages=[ChatMessage(role="user", content=question)],
        )
        events = [event async for event in self.orchestrator.stream(request)]
        data_events = [event.payload for event in events if event.type is ChatEventType.DATA]
        return AcceptanceResult(self.tools.executed.copy(), data_events, events[-1].type.value)


@pytest.fixture()
def acceptance_harness() -> AcceptanceHarness:
    fake = AcceptanceFakeProvider(now=lambda: NOW)
    counting = CountingProviderWrapper(fake)
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(counting, cache, now=lambda: NOW, timezone="Asia/Macau")
    tools = RecordingBusinessTools(service)
    model = FakeChatModel()
    orchestrator = ChatOrchestrator(tools, model)
    return AcceptanceHarness(orchestrator, tools, fake.live_match.id, counting, model)


@pytest.mark.parametrize(
    ("scope", "question", "expected_tool"),
    [
        ("global", "今晚 Sinner 几点打？", "find_player_matches"),
        ("global", "Alcaraz 今天有比赛吗？", "find_player_matches"),
        ("global", "Djokovic 下一场对谁？", "find_player_matches"),
        ("match", "这是什么赛事？", "get_match"),
        ("match", "第几轮？", "get_match"),
        ("match", "什么场地？", "get_match"),
        ("match", "比赛开始了吗？", "get_match"),
        ("match", "现在比分多少？", "get_match"),
        ("match", "谁在发球？", "get_match"),
    ],
)
@pytest.mark.asyncio
async def test_supported_acceptance_intents(
    scope: str,
    question: str,
    expected_tool: str,
    acceptance_harness: AcceptanceHarness,
) -> None:
    result = await acceptance_harness.ask(
        question,
        scope=scope,
        match_id=acceptance_harness.live_match_id if scope == "match" else None,
    )
    assert result.executed_tool_names == [expected_tool]
    assert result.data_events[0]["matches"]
    assert result.terminal_event == "done"


@pytest.mark.asyncio
async def test_historical_question_is_typed_unsupported_without_calls(
    acceptance_harness: AcceptanceHarness,
) -> None:
    result = await acceptance_harness.ask("昨天 Sinner 赢了吗？", scope="global", match_id=None)

    assert result.data_events[0]["kind"] == "unsupported"
    assert result.executed_tool_names == []
    assert acceptance_harness.provider_calls.calls == 0
    assert acceptance_harness.model.choose_calls == []
    assert result.terminal_event == "done"
