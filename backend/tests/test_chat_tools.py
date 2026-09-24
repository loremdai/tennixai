from datetime import datetime, timezone

import pytest

from app.cache import AsyncTTLCache
from app.chat.models import (
    ChatContext,
    ChatMessage,
    ChatRequest,
    ChatScope,
    PlayerHistoryEmptyReason,
    StructuredToolResult,
)
from app.chat.history import HistoryCapability, classify_history_capabilities
from app.chat.orchestrator import _catalog_for_request
from app.chat.tools import BusinessTools
from app.domain import CapabilityStatus, Match, MatchStatus, Player
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.intelligence import IntelligenceTopic
from app.providers.fake import FakeTennisProvider
from app.service import TennisService

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def fake_provider() -> FakeTennisProvider:
    return await FakeTennisProvider.create(
        identities=MemoryIdentityRepository(), now=lambda: NOW
    )


@pytest.fixture()
def service(fake_provider: FakeTennisProvider) -> TennisService:
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    return TennisService(fake_provider, cache, now=lambda: NOW, timezone="Asia/Shanghai")


@pytest.fixture()
def tools(service: TennisService) -> BusinessTools:
    return BusinessTools(service)


@pytest.fixture()
def known_match_id(fake_provider: FakeTennisProvider) -> str:
    return fake_provider.live_match.id


GLOBAL = ChatContext(scope="global")


def test_tool_catalog_exposes_the_p2_surface(tools: BusinessTools) -> None:
    catalog = tools.catalog()
    assert [item["function"]["name"] for item in catalog] == [
        "find_player_matches",
        "get_live_matches",
        "get_match",
        "get_match_intelligence",
        "get_player_results",
        "get_player_season_record",
        "get_head_to_head",
    ]
    scope = catalog[0]["function"]["parameters"]["properties"]["time_scope"]
    assert scope["enum"] == ["today", "tonight", "next"]


def test_p2_tool_schemas_inline_topics_and_bounds(tools: BusinessTools) -> None:
    catalog = {item["function"]["name"]: item for item in tools.catalog()}

    topic = catalog["get_match_intelligence"]["function"]["parameters"]["properties"]["topic"]
    assert topic["enum"] == [item.value for item in IntelligenceTopic]

    history = catalog["get_player_results"]["function"]["parameters"]
    assert history["properties"]["scope"]["enum"] == ["yesterday", "last", "recent"]
    assert history["properties"]["limit"]["minimum"] == 1
    assert history["properties"]["limit"]["maximum"] == 10


def test_catalog_items_have_function_shape_and_descriptions(tools: BusinessTools) -> None:
    for item in tools.catalog():
        assert item["type"] == "function"
        assert set(item["function"].keys()) == {"name", "description", "parameters"}
        assert item["function"]["description"]

    parameters = tools.catalog()[1]["function"]["parameters"]
    assert "player_name" in parameters["properties"]


def test_global_catalog_hides_match_only_tool(tools: BusinessTools) -> None:
    catalog = _catalog_for_request(
        tools.catalog(),
        ChatRequest(scope=ChatScope.GLOBAL, messages=[ChatMessage(role="user", content="现在有什么比赛？")]),
        classify_history_capabilities("现在有什么比赛？", scope=ChatScope.GLOBAL),
    )
    names = {item["function"]["name"] for item in catalog}

    assert "get_match_intelligence" not in names


def test_global_get_match_schema_requires_explicit_id(tools: BusinessTools) -> None:
    item = next(
        item for item in tools.catalog(
            names=("get_match",),
            scope=ChatScope.GLOBAL,
        )
        if item["function"]["name"] == "get_match"
    )

    assert item["function"]["parameters"]["required"] == ["match_id"]


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
async def test_match_intelligence_uses_page_context_and_returns_answer_metadata(
    tools: BusinessTools, known_match_id: str
) -> None:
    result = await tools.execute(
        "get_match_intelligence",
        {"topic": "momentum"},
        ChatContext(scope=ChatScope.MATCH, match_id=known_match_id),
    )

    assert result.kind == "intelligence"
    assert result.packet is not None
    assert result.packet.topic is IntelligenceTopic.MOMENTUM
    assert result.packet.match_id == known_match_id
    assert result.answer_context is not None
    assert result.answer_context.match_id == known_match_id
    assert result.answer_context.state_version == result.packet.state_version


@pytest.mark.asyncio
async def test_match_intelligence_requires_page_context(tools: BusinessTools) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute("get_match_intelligence", {"topic": "score"}, GLOBAL)

    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_player_results_yesterday_keeps_empty_availability(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "get_player_results",
        {"player_name": "Sinner", "scope": "yesterday", "limit": 3},
        GLOBAL,
    )

    assert result.kind == "player_history"
    assert result.matches == []
    assert result.player_history is not None
    assert result.player_history.scope == "yesterday"
    assert result.player_history.availability is CapabilityStatus.AVAILABLE


@pytest.mark.asyncio
async def test_player_results_recent_uses_five_season_window(
    tools: BusinessTools, fake_provider: FakeTennisProvider
) -> None:
    result = await tools.execute(
        "get_player_results",
        {"player_name": "Sinner", "scope": "recent", "limit": 3},
        GLOBAL,
    )

    assert result.kind == "player_history"
    assert result.player_history is not None
    assert result.player_history.scope == "recent"
    assert result.player_history.availability is CapabilityStatus.AVAILABLE
    sinner = next(
        player for player in fake_provider._players if player.name == "Jannik Sinner"
    )
    expected = sorted(
        (
            match
            for match in fake_provider.finished_results
            if any(player.id == sinner.id for player in match.players)
        ),
        key=lambda match: (match.scheduled_at, match.id),
        reverse=True,
    )[:3]
    assert [match.id for match in result.matches] == [
        match.id for match in expected
    ]
    assert all(match.status.value == "finished" for match in result.matches)


@pytest.mark.asyncio
async def test_head_to_head_resolves_both_names(tools: BusinessTools) -> None:
    result = await tools.execute(
        "get_head_to_head",
        {
            "first_player_name": "Sinner",
            "second_player_name": "Alcaraz",
            "limit": 2,
        },
        GLOBAL,
    )

    assert result.kind == "matches"
    assert result.matches == []
    assert result.metadata["availability"] == "available"


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
async def test_unknown_name_without_resolver_is_recoverable_resolution(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "find_player_matches",
        {"player_name": "Federer", "time_scope": "next"},
        GLOBAL,
    )
    assert result.kind == "player_resolution"
    assert result.resolution is not None
    assert result.resolution.status.value == "not_found"


def test_historical_query_is_rejected_without_calling_model() -> None:
    capabilities = classify_history_capabilities(
        "昨天 Sinner 赢了吗？", scope=ChatScope.GLOBAL
    )
    assert HistoryCapability.LIMITED_RESULTS in capabilities
    assert classify_history_capabilities(
        "Sinner tonight?", scope=ChatScope.GLOBAL
    ) == frozenset()


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
        assert classify_history_capabilities(
            f"...{phrase}...", scope=ChatScope.GLOBAL
        ), phrase

    assert classify_history_capabilities(
        "今晚 Sinner 几点打？", scope=ChatScope.GLOBAL
    ) == frozenset()
    assert classify_history_capabilities(
        "What is the score now?", scope=ChatScope.GLOBAL
    ) == frozenset()


def test_broad_history_guard_keeps_bounded_h2h_supported() -> None:
    from app.chat.history import is_broad_history_only

    assert is_broad_history_only(
        classify_history_capabilities("Sinner 的历史战绩", scope=ChatScope.GLOBAL)
    )
    assert not is_broad_history_only(
        classify_history_capabilities(
            "Sinner 和 Alcaraz 的历史交手", scope=ChatScope.GLOBAL
        )
    )
    assert is_broad_history_only(
        classify_history_capabilities("Sinner 的 career history", scope=ChatScope.GLOBAL)
    )


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


# ---------------------------------------------------------------- T50 resolver


@pytest.fixture()
async def resolver_service(fake_provider: FakeTennisProvider):
    from app.players.models import RankingEntry, RankingMovement, Tour
    from app.players.normalization import derive_english_aliases
    from app.players.repository import MemoryPlayerDirectoryRepository
    from app.players.resolver import PlayerResolver

    directory = MemoryPlayerDirectoryRepository()
    entries = []
    for index, player in enumerate(fake_provider._players):
        entries.append(
            RankingEntry(
                player=player,
                tour=Tour.WTA if player.id in {
                    fake_provider._players[6].id, fake_provider._players[7].id
                } else Tour.ATP,
                rank=player.ranking or 900 + index,
                points=100,
                movement=RankingMovement.SAME,
                ranking_date=NOW.date(),
                fetched_at=NOW,
            )
        )
    wang_a = Player(id="ply_wang_a", name="Xinyu Wang", ranking=25)
    wang_b = Player(id="ply_wang_b", name="Xiyu Wang", ranking=50)
    entries.append(
        RankingEntry(player=wang_a, tour=Tour.WTA, rank=25, points=90,
                     movement=RankingMovement.SAME, ranking_date=NOW.date(), fetched_at=NOW)
    )
    entries.append(
        RankingEntry(player=wang_b, tour=Tour.WTA, rank=50, points=80,
                     movement=RankingMovement.SAME, ranking_date=NOW.date(), fetched_at=NOW)
    )
    await directory.save_ranking_snapshot(tuple(entries))
    for directory_player in await directory.list_players_for_alias_sync(limit=100):
        await directory.upsert_aliases(derive_english_aliases(directory_player))
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    service = TennisService(
        fake_provider,
        cache,
        now=lambda: NOW,
        timezone="Asia/Shanghai",
        directory=directory,
        resolver=PlayerResolver(directory),
    )
    return service, directory


def _match_context(directory_players: tuple[Player, ...], match_id: str) -> ChatContext:
    from app.domain import DataFreshness, MatchStatus, Tournament
    from app.domain import MatchSnapshot

    match = Match(
        id=match_id,
        status=MatchStatus.LIVE,
        players=directory_players,
        tournament=Tournament(id="trn_ctx", name="Context Event", tour="wta"),
        scheduled_at=NOW,
        freshness=DataFreshness(provider="fake", observed_at=NOW),
    )
    snapshot = MatchSnapshot(match=match, quality=(), state_version=0, as_of=NOW)
    return ChatContext(scope=ChatScope.MATCH, match_id=match_id, snapshot=snapshot)


@pytest.mark.asyncio
async def test_unknown_name_returns_recoverable_resolution(resolver_service) -> None:
    service, _ = resolver_service
    tools = BusinessTools(service)

    result = await tools.execute(
        "find_player_matches", {"player_name": "Federer", "time_scope": "next"}, GLOBAL
    )

    assert result.kind == "player_resolution"
    assert result.resolution is not None
    assert result.resolution.status.value == "not_found"


@pytest.mark.asyncio
async def test_ambiguous_surname_returns_candidates_result(resolver_service) -> None:
    service, _ = resolver_service
    tools = BusinessTools(service)

    result = await tools.execute(
        "find_player_matches", {"player_name": "Wang", "time_scope": "next"}, GLOBAL
    )

    assert result.kind == "player_resolution"
    assert result.resolution is not None
    assert result.resolution.status.value == "ambiguous"
    assert {c.player.id for c in result.resolution.candidates} == {
        "ply_wang_a",
        "ply_wang_b",
    }


@pytest.mark.asyncio
async def test_match_context_resolves_unique_participant(resolver_service, fake_provider) -> None:
    service, directory = resolver_service
    tools = BusinessTools(service)
    wang_a = Player(id="ply_wang_a", name="Xinyu Wang", ranking=25)
    wang_b = Player(id="ply_wang_b", name="Xiyu Wang", ranking=50)
    context = _match_context((wang_a, wang_b), fake_provider.live_match.id)

    result = await tools.execute(
        "find_player_matches", {"player_name": "Wang", "time_scope": "next"}, context
    )

    # Both players participate, so the surname stays ambiguous even in context.
    assert result.kind == "player_resolution"

    single = _match_context((wang_a, fake_provider._players[0]), fake_provider.live_match.id)
    resolved = await tools.execute(
        "find_player_matches", {"player_name": "Wang", "time_scope": "next"}, single
    )
    assert resolved.kind == "matches"


@pytest.mark.asyncio
async def test_live_matches_filter_uses_resolver(resolver_service) -> None:
    service, _ = resolver_service
    tools = BusinessTools(service)

    result = await tools.execute(
        "get_live_matches", {"player_name": "Sinner"}, GLOBAL
    )
    assert result.kind == "matches"

    missing = await tools.execute(
        "get_live_matches", {"player_name": "Federer"}, GLOBAL
    )
    assert missing.kind == "player_resolution"


@pytest.mark.asyncio
async def test_head_to_head_stops_on_first_unresolved_side(resolver_service) -> None:
    service, _ = resolver_service
    tools = BusinessTools(service)

    result = await tools.execute(
        "get_head_to_head",
        {"first_player_name": "Sinner", "second_player_name": "Federer", "limit": 2},
        GLOBAL,
    )
    assert result.kind == "player_resolution"
    assert result.resolution is not None
    assert result.resolution.status.value == "not_found"


# ------------------------------------------------- T54 typed player_history


@pytest.mark.asyncio
async def test_history_tools_have_exact_schemas(tools: BusinessTools) -> None:
    catalog = {item["function"]["name"]: item for item in tools.catalog()}

    results_params = catalog["get_player_results"]["function"]["parameters"]
    assert results_params["required"] == ["player_name", "scope"]
    assert results_params["properties"]["player_name"] == {
        "minLength": 1,
        "title": "Player Name",
        "type": "string",
    }
    assert results_params["properties"]["scope"] == {
        "enum": ["yesterday", "last", "recent"],
        "title": "PlayerResultsScope",
        "type": "string",
    }
    assert results_params["properties"]["limit"] == {
        "default": 5,
        "maximum": 10,
        "minimum": 1,
        "title": "Limit",
        "type": "integer",
    }

    season_params = catalog["get_player_season_record"]["function"]["parameters"]
    assert season_params["required"] == ["player_name"]
    assert season_params["properties"]["player_name"] == {
        "minLength": 1,
        "title": "Player Name",
        "type": "string",
    }
    assert season_params["properties"]["season"] == {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
        "default": None,
        "title": "Season",
    }


def test_history_tool_descriptions_state_semantics(tools: BusinessTools) -> None:
    catalog = {item["function"]["name"]: item for item in tools.catalog()}
    results_description = catalog["get_player_results"]["function"]["description"]
    assert "last" in results_description
    assert "recent" in results_description
    assert "one call per player" in results_description

    season_description = catalog["get_player_season_record"]["function"]["description"]
    assert "season" in season_description


def test_system_prompt_states_history_semantics() -> None:
    from app.chat.orchestrator import GLOBAL_SYSTEM_PROMPT

    assert "赛果" in GLOBAL_SYSTEM_PROMPT
    assert "上一场" in GLOBAL_SYSTEM_PROMPT
    assert "每位球员单独调用" in GLOBAL_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_player_results_last_returns_typed_history_context(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "get_player_results",
        {"player_name": "Sinner", "scope": "last", "limit": 5},
        GLOBAL,
    )

    assert result.kind == "player_history"
    assert result.metadata == {}
    context = result.player_history
    assert context is not None
    assert context.player.name == "Jannik Sinner"
    assert context.scope == "last"
    assert context.season is None
    assert context.availability is CapabilityStatus.AVAILABLE
    assert context.season_record is None
    assert context.empty_reason is None
    # `last` normalizes any model-supplied limit to exactly one match.
    assert len(result.matches) == 1
    assert result.matches[0].status is MatchStatus.FINISHED


@pytest.mark.asyncio
async def test_player_results_empty_sets_typed_empty_reason(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "get_player_results",
        {"player_name": "Sinner", "scope": "yesterday", "limit": 5},
        GLOBAL,
    )

    assert result.kind == "player_history"
    assert result.matches == []
    context = result.player_history
    assert context is not None
    assert context.scope == "yesterday"
    assert context.availability is CapabilityStatus.AVAILABLE
    assert context.empty_reason is PlayerHistoryEmptyReason.NO_RESULTS_IN_SCOPE


@pytest.mark.asyncio
async def test_player_history_carries_bilingual_identity(
    resolver_service, fake_provider: FakeTennisProvider
) -> None:
    from app.players.models import (
        LocalizedNameUpdate,
        PlayerAlias,
        PlayerAliasKind,
        PlayerAliasSource,
    )
    from app.players.normalization import normalize_player_name

    service, directory = resolver_service
    sinner = next(
        player for player in fake_provider._players if player.name == "Jannik Sinner"
    )
    zh_alias = PlayerAlias(
        player_id=sinner.id,
        locale="zh-Hans",
        alias="辛纳",
        normalized_alias=normalize_player_name("辛纳"),
        kind=PlayerAliasKind.PREFERRED,
        source=PlayerAliasSource.LLM,
    )
    await directory.save_localized_names(
        (
            LocalizedNameUpdate(
                player_id=sinner.id,
                localized_name="辛纳",
                aliases=(zh_alias,),
            ),
        )
    )
    tools = BusinessTools(service)

    result = await tools.execute(
        "get_player_results",
        {"player_name": "辛纳", "scope": "last"},
        GLOBAL,
    )

    assert result.kind == "player_history"
    context = result.player_history
    assert context is not None
    assert context.player.id == sinner.id
    assert context.player.name == "Jannik Sinner"
    assert context.player.localized_name == "辛纳"


@pytest.mark.asyncio
async def test_season_record_returns_selected_year_and_supplier_record(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "get_player_season_record",
        {"player_name": "Sinner"},
        GLOBAL,
    )

    assert result.kind == "player_history"
    assert result.matches == []
    context = result.player_history
    assert context is not None
    assert context.player.name == "Jannik Sinner"
    assert context.scope == "season"
    assert context.season == 2026
    assert context.availability is CapabilityStatus.AVAILABLE
    assert context.empty_reason is None
    assert context.season_record is not None
    assert context.season_record.season == 2026
    assert context.season_record.matches_won == 30


@pytest.mark.asyncio
async def test_season_record_absent_is_typed_unavailable() -> None:
    class SingleSeasonProvider(FakeTennisProvider):
        async def get_player_profile(self, player_id: str):
            profile = await super().get_player_profile(player_id)
            return profile.model_copy(
                update={
                    "seasons": tuple(
                        record for record in profile.seasons if record.season == 2026
                    )
                }
            )

    provider = await SingleSeasonProvider.create(
        identities=MemoryIdentityRepository(), now=lambda: NOW
    )
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=64)
    service = TennisService(
        provider, cache, now=lambda: NOW, timezone="Asia/Shanghai"
    )
    tools = BusinessTools(service)

    result = await tools.execute(
        "get_player_season_record",
        {"player_name": "Sinner", "season": 2025},
        GLOBAL,
    )

    assert result.kind == "player_history"
    context = result.player_history
    assert context is not None
    assert context.scope == "season"
    assert context.season == 2025
    assert context.season_record is None
    assert context.availability is CapabilityStatus.UNAVAILABLE
    assert (
        context.empty_reason is PlayerHistoryEmptyReason.SEASON_RECORD_UNAVAILABLE
    )


@pytest.mark.asyncio
async def test_season_record_out_of_window_is_invalid_request(
    tools: BusinessTools,
) -> None:
    with pytest.raises(AppError) as error_info:
        await tools.execute(
            "get_player_season_record",
            {"player_name": "Sinner", "season": 2019},
            GLOBAL,
        )
    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_season_record_unknown_player_is_recoverable_resolution(
    tools: BusinessTools,
) -> None:
    result = await tools.execute(
        "get_player_season_record",
        {"player_name": "Federer"},
        GLOBAL,
    )
    assert result.kind == "player_resolution"
    assert result.resolution is not None
    assert result.resolution.status.value == "not_found"
