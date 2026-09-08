from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.models import (
    ChatContext,
    ChatMessage,
    ChatRequest,
    ChatScope,
    StructuredToolResult,
)
from app.chat.tools import BusinessTools, is_historical_query
from app.domain import Match
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def fake_provider() -> FakeTennisProvider:
    return FakeTennisProvider(identities=MemoryIdentityRepository(), now=lambda: NOW)


@pytest.fixture()
def service(fake_provider: FakeTennisProvider) -> TennisService:
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    return TennisService(fake_provider, cache, now=lambda: NOW, timezone="Asia/Macau")


@pytest.fixture()
def tools(service: TennisService) -> BusinessTools:
    return BusinessTools(service)


@pytest.fixture()
def known_match_id(fake_provider: FakeTennisProvider) -> str:
    return fake_provider.live_match.id


GLOBAL = ChatContext(scope="global")


def test_tool_catalog_is_exactly_p1_surface(tools: BusinessTools) -> None:
    catalog = tools.catalog()
    assert [item["function"]["name"] for item in catalog] == [
        "find_player_matches", "get_live_matches", "get_match"
    ]
    scope = catalog[0]["function"]["parameters"]["properties"]["time_scope"]
    assert scope["enum"] == ["today", "tonight", "next"]


def test_catalog_items_have_function_shape_and_descriptions(tools: BusinessTools) -> None:
    for item in tools.catalog():
        assert item["type"] == "function"
        assert set(item["function"].keys()) == {"name", "description", "parameters"}
        assert item["function"]["description"]

    parameters = tools.catalog()[1]["function"]["parameters"]
    assert "player_name" in parameters["properties"]


@pytest.mark.asyncio
async def test_match_scope_injects_match_id(tools: BusinessTools, known_match_id: str) -> None:
    result = await tools.execute("get_match", {}, ChatContext(scope="match", match_id=known_match_id))
    assert result.matches[0].id == known_match_id


@pytest.mark.asyncio
async def test_match_scope_ignores_model_supplied_match_id(
    tools: BusinessTools, known_match_id: str
) -> None:
    result = await tools.execute(
        "get_match",
        {"match_id": "mat_something_else"},
        ChatContext(scope="match", match_id=known_match_id),
    )
    assert result.kind == "match"
    assert result.matches[0].id == known_match_id


@pytest.mark.asyncio
async def test_global_get_match_requires_match_id(tools: BusinessTools) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute("get_match", {}, GLOBAL)
    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_find_player_matches_tonight_returns_canonical_matches(
    tools: BusinessTools, fake_provider: FakeTennisProvider
) -> None:
    result = await tools.execute(
        "find_player_matches",
        {"player_name": "Sinner", "time_scope": "tonight"},
        GLOBAL,
    )

    assert result.kind == "matches"
    ids = {match.id for match in result.matches}
    assert ids == {fake_provider.sinner_alcaraz.id, fake_provider.live_match.id}
    assert all(isinstance(match, Match) for match in result.matches)


@pytest.mark.asyncio
async def test_find_player_matches_next_returns_single_scheduled(
    tools: BusinessTools, fake_provider: FakeTennisProvider
) -> None:
    result = await tools.execute(
        "find_player_matches",
        {"player_name": "Sinner", "time_scope": "next"},
        GLOBAL,
    )

    assert result.kind == "matches"
    assert [match.id for match in result.matches] == [fake_provider.sinner_alcaraz.id]


@pytest.mark.asyncio
async def test_get_live_matches_optional_player_filter(
    tools: BusinessTools, fake_provider: FakeTennisProvider
) -> None:
    all_live = await tools.execute("get_live_matches", {}, GLOBAL)
    assert all_live.kind == "matches"
    assert [match.id for match in all_live.matches] == [fake_provider.live_match.id]

    djokovic_live = await tools.execute("get_live_matches", {"player_name": "Djokovic"}, GLOBAL)
    assert djokovic_live.matches == []


@pytest.mark.asyncio
async def test_malformed_args_yield_invalid_request(tools: BusinessTools) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute(
            "find_player_matches",
            {"player_name": "", "time_scope": "tonight"},
            GLOBAL,
        )
    error = error_info.value
    assert error.code == "invalid_request"
    assert error.status_code == 422
    assert error.details == {"tool": "find_player_matches"}

    with pytest.raises(AppError) as enum_error:
        await tools.execute(
            "find_player_matches",
            {"player_name": "Sinner", "time_scope": "last_week"},
            GLOBAL,
        )
    assert enum_error.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected(tools: BusinessTools) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute("place_bet", {}, GLOBAL)
    assert error_info.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_service_errors_propagate_through_tools(tools: BusinessTools) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute(
            "find_player_matches",
            {"player_name": "Federer", "time_scope": "next"},
            GLOBAL,
        )
    assert error_info.value.code == "not_found"


def test_historical_query_is_rejected_without_calling_model() -> None:
    assert is_historical_query("昨天 Sinner 赢了吗？") is True
    assert is_historical_query("Sinner tonight?") is False


def test_historical_guard_covers_all_p1_phrases_case_insensitively() -> None:
    for phrase in [
        "昨天",
        "昨日",
        "上一场",
        "最近一场",
        "历史",
        "YESTERDAY",
        "Last Match",
        "PREVIOUS MATCH",
        "History",
    ]:
        assert is_historical_query(f"...{phrase}...") is True

    assert is_historical_query("今晚 Sinner 几点打？") is False
    assert is_historical_query("What is the score now?") is False


def test_structured_unsupported_result_shape() -> None:
    result = StructuredToolResult(kind="unsupported")
    assert result.kind == "unsupported"
    assert result.matches == []


def test_chat_request_bounds() -> None:
    request = ChatRequest(
        scope="match",
        match_id="mat_1",
        messages=[ChatMessage(role="user", content="谁在发球？")],
    )
    assert request.scope is ChatScope.MATCH

    with pytest.raises(Exception):
        ChatRequest(scope="global", messages=[])

    with pytest.raises(Exception):
        ChatRequest(
            scope="global",
            messages=[ChatMessage(role="user", content="q")] * 13,
        )

    with pytest.raises(Exception):
        ChatMessage(role="user", content="x" * 4001)
