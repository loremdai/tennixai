"""Opt-in real LLM smoke for offline Chinese-name enrichment.

Run with:
    TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE=1 uv run pytest -m player_alias_llm_live \
        tests/live/test_player_alias_enrichment_live.py -v

Uses dedicated fixture players in an in-memory repository: nothing is written
to PostgreSQL, and no vendor IDs or raw payloads are sent to the model.
"""

import os
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.domain import Player
from app.players.enrichment import OpenAICompatibleTranslator, PlayerAliasEnricher
from app.players.models import RankingEntry, RankingMovement, Tour
from app.players.repository import MemoryPlayerDirectoryRepository

pytestmark = pytest.mark.player_alias_llm_live

FIXED_NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


def _require_enabled() -> Settings:
    if os.environ.get("TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE") != "1":
        pytest.skip("TENNIX_RUN_PLAYER_ALIAS_LLM_LIVE not set")
    settings = Settings(provider_mode="fake", llm_mode="fake")
    if (
        settings.llm_api_key is None
        or not settings.llm_api_key.get_secret_value().strip()
        or not settings.llm_base_url
    ):
        pytest.skip("LLM endpoint not configured in root .env")
    return settings


def _entry(player_id: str, name: str, rank: int) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, country_code="usa", ranking=rank),
        tour=Tour.ATP,
        rank=rank,
        points=1000 - rank,
        movement=RankingMovement.SAME,
        ranking_date=FIXED_NOW.date(),
        fetched_at=FIXED_NOW,
    )


@pytest.mark.asyncio
async def test_real_llm_translates_bounded_batch_and_rerun_makes_no_calls() -> None:
    settings = _require_enabled()
    repository = MemoryPlayerDirectoryRepository()
    await repository.save_ranking_snapshot(
        (
            _entry("ply_live_shelton", "Ben Shelton", 5),
            _entry("ply_live_zheng", "Qinwen Zheng", 5),
        )
    )
    translator = OpenAICompatibleTranslator(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url or "",
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    enricher = PlayerAliasEnricher(repository, translator, model=settings.llm_model)

    first = await enricher.enrich_missing(batch_size=2)
    assert first.translated == 2
    assert first.failed == 0
    for player_id in ("ply_live_shelton", "ply_live_zheng"):
        directory_player = await repository.get_player(player_id)
        assert directory_player is not None
        localized = directory_player.player.localized_name
        assert localized
        assert any("一" <= char <= "鿿" for char in localized)

    second = await enricher.enrich_missing(batch_size=2)
    assert second.translated == 0
    assert second.batches == 0
    assert translator.request_count == 1
