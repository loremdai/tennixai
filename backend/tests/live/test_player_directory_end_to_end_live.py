"""Opt-in real-service directory end-to-end gate (T52).

Run with:
    TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE=1 uv run pytest -m player_directory_e2e_live \
        tests/live/test_player_directory_end_to_end_live.py -v

Prerequisites against the local compose PostgreSQL (run once, in order):
    docker compose up -d --wait postgres
    uv run alembic upgrade head
    uv run python -m app.players.cli sync
    uv run python -m app.players.cli enrich-zh --batch-size 25

The gate performs one bounded real ranking sync (both tours), reads the
already-enriched local directory through the runtime PlayerResolver, and
verifies one profile plus one season result page. It never writes aliases or
localized names, makes no LLM call, and never prints vendor identifiers:
assertions and failure output carry internal IDs and counts only.
"""

import os
from datetime import datetime, timezone

import httpx
import pytest

from app.cache import AsyncTTLCache
from app.config import Settings
from app.persistence.database import Database
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.players.models import ResultOutcome
from app.players.resolver import PlayerResolver
from app.players.sync import PlayerDirectorySync
from app.providers.api_tennis import ApiTennisProvider
from app.service import TennisService

pytestmark = pytest.mark.player_directory_e2e_live

ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("Ben Shelton", "B. Shelton", "Shelton", "本·谢尔顿", "谢尔顿"),
    ("Qinwen Zheng", "Zheng Qinwen", "Q. Zheng", "郑钦文"),
    ("Novak Djokovic", "N. Djokovic", "Djokovic", "德约科维奇"),
)


def _require_enabled() -> tuple[Settings, str]:
    if os.environ.get("TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE") != "1":
        pytest.skip("TENNIX_RUN_PLAYER_DIRECTORY_E2E_LIVE not set")
    settings = Settings(provider_mode="fake", llm_mode="fake")
    key = settings.api_tennis_api_key
    if key is None or not key.get_secret_value().strip():
        pytest.skip("TENNIX_API_TENNIS_API_KEY not configured in root .env")
    return settings, key.get_secret_value()


@pytest.fixture()
async def live_directory():
    """One bounded real sync into the local PostgreSQL directory, read-only after."""
    settings, api_key = _require_enabled()
    database = Database(settings.database_url)
    try:
        async with database.engine.connect() as connection:
            from sqlalchemy import text

            mapped = await connection.execute(
                text("SELECT to_regclass('public.player_aliases')")
            )
            if mapped.scalar() is None:
                pytest.skip("player directory schema not migrated; run alembic upgrade head")
    except Exception as exc:  # pragma: no cover - environment dependent
        await database.dispose()
        pytest.skip(
            "PostgreSQL not reachable at TENNIX_DATABASE_URL "
            f"({type(exc).__name__}); start compose services"
        )

    repository = PostgresPlayerDirectoryRepository(database)
    identities = PostgresIdentityRepository(database)
    client = httpx.AsyncClient(
        base_url=settings.api_tennis_base_url, timeout=30.0, trust_env=False
    )
    provider = ApiTennisProvider(
        client=client,
        identities=identities,
        api_key=api_key,
        now=lambda: datetime.now(timezone.utc),
    )
    try:
        report = await PlayerDirectorySync(
            provider, repository, now=lambda: datetime.now(timezone.utc)
        ).sync_rankings()
    except Exception as exc:  # pragma: no cover - network dependent
        await client.aclose()
        await database.dispose()
        pytest.skip(f"API-Tennis unreachable during bounded sync ({type(exc).__name__})")
    if report.failed:
        await client.aclose()
        await database.dispose()
        pytest.skip(
            f"API-Tennis sync incomplete during gate ({report.failed} tour(s) failed); "
            "rerun once the supplier connection is stable"
        )
    try:
        yield repository, provider
    finally:
        await client.aclose()
        await database.dispose()


@pytest.mark.asyncio
async def test_alias_matrix_resolves_to_stable_internal_ids(live_directory) -> None:
    repository, _ = live_directory
    resolver = PlayerResolver(repository)

    group_ids: list[str] = []
    for group in ALIAS_GROUPS:
        resolved_ids: set[str] = set()
        for query in group:
            resolution = await resolver.resolve(query)
            assert resolution.status.value == "resolved", (
                f"alias {query!r} must resolve in the enriched directory, "
                f"got {resolution.status.value}"
            )
            assert resolution.player is not None
            resolved_ids.add(resolution.player.id)
        assert len(resolved_ids) == 1, f"alias group {group} mapped to {resolved_ids}"
        group_ids.append(resolved_ids.pop())

    assert len(set(group_ids)) == len(group_ids), "alias groups must stay distinct"
    for internal_id in group_ids:
        assert internal_id.startswith("ply_")


@pytest.mark.asyncio
async def test_ambiguous_surname_still_returns_candidates(live_directory) -> None:
    repository, _ = live_directory
    resolver = PlayerResolver(repository)

    resolution = await resolver.resolve("Wang")
    assert resolution.status.value in {"ambiguous", "resolved"}
    if resolution.status.value == "ambiguous":
        assert len(resolution.candidates) >= 2
        for candidate in resolution.candidates:
            assert candidate.player.id.startswith("ply_")


@pytest.mark.asyncio
async def test_profile_and_season_results_honest_shape(live_directory) -> None:
    repository, provider = live_directory

    # Reuse the resolved Ben Shelton internal ID; profile/results go through
    # the provider by internal ID only.
    resolver = PlayerResolver(repository)
    resolution = await resolver.resolve("Ben Shelton")
    assert resolution.player is not None
    internal_id = resolution.player.id

    profile = await provider.get_player_profile(internal_id)
    assert profile.player.id == internal_id
    # The supplier history may be longer than the product window; every
    # record still carries honest non-negative counts.
    assert profile.seasons
    for record in profile.seasons:
        assert record.matches_won >= 0 and record.matches_lost >= 0

    service = TennisService(
        provider,
        AsyncTTLCache(max_entries=8),
        now=lambda: datetime.now(timezone.utc),
        timezone="Asia/Shanghai",
        directory=repository,
    )
    current_year = datetime.now(timezone.utc).year
    view = await service.get_player_profile_view(internal_id)
    assert len(view.profile.seasons) <= 5
    assert all(
        current_year - 4 <= record.season <= current_year
        for record in view.profile.seasons
    )

    results = await service.get_player_result_page(
        internal_id,
        season=current_year,
        tiers=(),
        outcome=ResultOutcome.ALL,
        page=1,
    )
    assert results.page_size == 20
    # An empty supplier window is an honest result, not a failure.
    for match in results.matches:
        assert match.id
        assert all(player.id.startswith("ply_") for player in match.players)


# ------------------------------------------------------------------ T54 history


def _require_llm_credentials() -> tuple[str, str, str]:
    settings = Settings(provider_mode="fake", llm_mode="fake")
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url
    if api_key is None or not api_key.get_secret_value().strip() or not base_url:
        pytest.skip("TENNIX_LLM_API_KEY / TENNIX_LLM_BASE_URL not configured")
    return api_key.get_secret_value(), base_url, settings.llm_model


def _history_payloads(events) -> list[dict]:
    from app.chat.models import ChatEventType

    return [
        event.payload
        for event in events
        if event.type is ChatEventType.DATA
        and event.payload.get("kind") == "player_history"
    ]


def _assert_finished_and_ordered(matches: list[dict]) -> None:
    assert all(match["status"] == "finished" for match in matches)
    scheduled = [match["scheduled_at"] for match in matches]
    assert scheduled == sorted(scheduled, reverse=True)


@pytest.mark.asyncio
async def test_home_history_chat_matches_probed_service_facts(live_directory) -> None:
    """Real API-Tennis facts probed first, then compared with real-LLM Chat output.

    Volatile supplier data is never frozen: every assertion compares against
    the canonical service result captured in the same run.
    """
    from app.chat.client import OpenAICompatibleChatModel
    from app.chat.models import ChatMessage, ChatRequest
    from app.chat.orchestrator import ChatOrchestrator
    from app.chat.tools import BusinessTools
    from app.players.resolver import PlayerResolver

    repository, provider = live_directory
    api_key, base_url, model_name = _require_llm_credentials()
    resolver = PlayerResolver(repository)

    zheng = await resolver.resolve("郑钦文")
    assert zheng.status.value == "resolved" and zheng.player is not None
    sinner = await resolver.resolve("辛纳")
    assert sinner.status.value == "resolved" and sinner.player is not None
    shelton = await resolver.resolve("Shelton")
    assert shelton.status.value == "resolved" and shelton.player is not None

    service = TennisService(
        provider,
        AsyncTTLCache(max_entries=32),
        now=lambda: datetime.now(timezone.utc),
        timezone="Asia/Shanghai",
        directory=repository,
        resolver=resolver,
    )

    # Same-run canonical probes.
    zheng_recent = await service.get_latest_player_results(zheng.player.id, limit=5)
    sinner_last = await service.get_latest_player_results(sinner.player.id, limit=1)
    shelton_last = await service.get_latest_player_results(shelton.player.id, limit=1)
    zheng_season, zheng_record = await service.get_player_season_record(zheng.player.id)

    orchestrator = ChatOrchestrator(
        BusinessTools(service),
        OpenAICompatibleChatModel(api_key=api_key, base_url=base_url, model=model_name),
    )

    async def stream(question: str):
        return [
            event
            async for event in orchestrator.stream(
                ChatRequest(
                    scope="global",
                    messages=[ChatMessage(role="user", content=question)],
                )
            )
        ]

    def check_completion(events) -> None:
        from app.chat.models import ChatEventType as CET

        assert not any(event.type is CET.ERROR for event in events)
        assert events[-1].type is CET.DONE

    # 1) single recent-results question
    events = await stream("郑钦文最近赛果如何？")
    payloads = _history_payloads(events)
    assert payloads, "expected typed player_history for the recent-results question"
    history = payloads[0]["player_history"]
    assert history["player"]["id"] == zheng.player.id
    assert history["scope"] == "recent"
    matches = payloads[0]["matches"]
    _assert_finished_and_ordered(matches)
    if zheng_recent:
        assert [match["id"] for match in matches] == [m.id for m in zheng_recent]
    else:
        assert matches == []
        assert history["empty_reason"] == "no_results_in_scope"
    check_completion(events)

    # 2) multi-player question keeps both structured results
    events = await stream("辛纳上一次比赛是什么时候？郑钦文赛果如何？")
    payloads = _history_payloads(events)
    assert len(payloads) == 2, "both players must keep their own structured result"
    by_player = {payload["player_history"]["player"]["id"]: payload for payload in payloads}
    assert set(by_player) == {sinner.player.id, zheng.player.id}
    sinner_payload = by_player[sinner.player.id]
    assert sinner_payload["player_history"]["scope"] == "last"
    _assert_finished_and_ordered(sinner_payload["matches"])
    assert [match["id"] for match in sinner_payload["matches"]] == [
        m.id for m in sinner_last
    ]
    zheng_payload = by_player[zheng.player.id]
    _assert_finished_and_ordered(zheng_payload["matches"])
    assert [match["id"] for match in zheng_payload["matches"]] == [
        m.id for m in zheng_recent
    ]
    check_completion(events)

    # 3) season-record question against the supplier profile
    events = await stream("郑钦文这个赛季战绩如何？")
    payloads = _history_payloads(events)
    assert payloads, "expected typed player_history for the season question"
    history = payloads[0]["player_history"]
    assert history["player"]["id"] == zheng.player.id
    assert history["scope"] == "season"
    assert history["season"] == zheng_season
    if zheng_record is not None:
        assert history["season_record"] is not None
        assert history["season_record"]["matches_won"] == zheng_record.matches_won
        assert history["season_record"]["matches_lost"] == zheng_record.matches_lost
    else:
        assert history["season_record"] is None
        assert history["empty_reason"] == "season_record_unavailable"
    check_completion(events)

    # 4) English last-match question
    events = await stream("Shelton last match")
    payloads = _history_payloads(events)
    assert payloads, "expected typed player_history for the English last-match question"
    history = payloads[0]["player_history"]
    assert history["player"]["id"] == shelton.player.id
    assert history["scope"] == "last"
    assert len(payloads[0]["matches"]) <= 1
    _assert_finished_and_ordered(payloads[0]["matches"])
    assert [match["id"] for match in payloads[0]["matches"]] == [
        m.id for m in shelton_last
    ]
    check_completion(events)
