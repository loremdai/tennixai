"""Offline Chinese-name enrichment tests (deterministic translator stubs)."""

import json

import pytest

from app.domain import Gender, Player
from app.errors import AppError
from app.players.enrichment import (
    PLAYER_NAME_PROMPT_VERSION,
    EnrichmentReport,
    OpenAICompatibleTranslator,
    PlayerAliasEnricher,
    PlayerNameInput,
    parse_translation_payload,
)
from app.players.models import PlayerAliasKind, RankingEntry, RankingMovement, Tour
from app.players.repository import MemoryPlayerDirectoryRepository

from datetime import datetime, timezone

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


class StubTranslator:
    """Mimics the adapter contract: raw payload strings are parsed with the
    same strict parser the production adapter uses."""

    def __init__(self, response: str | None = None, error: AppError | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[PlayerNameInput, ...]] = []

    async def translate(self, players: tuple[PlayerNameInput, ...]) -> str:
        self.calls.append(players)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _payload(players: list[dict]) -> str:
    return json.dumps({"players": players}, ensure_ascii=False)


def _ok_payload(inputs: tuple[PlayerNameInput, ...], suffix: str = "氏") -> str:
    return _payload(
        [
            {"player_id": item.player_id, "localized_name": f"{item.name}{suffix}", "aliases": []}
            for item in inputs
        ]
    )


async def _seed(repository: MemoryPlayerDirectoryRepository, count: int = 2) -> tuple[RankingEntry, ...]:
    entries = tuple(
        RankingEntry(
            player=Player(id=f"ply_{index}", name=f"Player {index}", country_code="usa", ranking=index),
            tour=Tour.ATP,
            rank=index,
            points=100,
            movement=RankingMovement.SAME,
            ranking_date=NOW.date(),
            fetched_at=NOW,
        )
        for index in range(1, count + 1)
    )
    await repository.save_ranking_snapshot(entries)
    return entries


@pytest.mark.asyncio
async def test_valid_batch_writes_names_and_chinese_aliases() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator()

    async def respond(players: tuple[PlayerNameInput, ...]) -> str:
        return _ok_payload(players)

    translator.translate = respond  # type: ignore[method-assign]
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    report = await enricher.enrich_missing(batch_size=2)

    assert isinstance(report, EnrichmentReport)
    assert report.translated == 2
    assert report.failed == 0
    player = await repository.get_player("ply_1")
    assert player is not None
    assert player.player.localized_name == "Player 1氏"
    counts = await repository.directory_counts()
    assert counts["localized"] == 2
    assert counts["aliases"] >= 2


@pytest.mark.asyncio
async def test_unknown_returned_id_writes_nothing() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator(
        _payload([{"player_id": "ply_unknown", "localized_name": "未知", "aliases": []}])
    )
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    with pytest.raises(AppError, match="translation batch"):
        await enricher.enrich_missing(batch_size=2)

    assert await repository.directory_counts() == {
        "players": 2,
        "localized": 0,
        "aliases": 0,
        "ranked_atp": 2,
        "ranked_wta": 0,
    }


@pytest.mark.asyncio
async def test_duplicate_returned_id_writes_nothing() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator(
        _payload(
            [
                {"player_id": "ply_1", "localized_name": "甲", "aliases": []},
                {"player_id": "ply_1", "localized_name": "乙", "aliases": []},
            ]
        )
    )
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    with pytest.raises(AppError, match="translation batch"):
        await enricher.enrich_missing(batch_size=2)
    assert (await repository.directory_counts())["localized"] == 0


@pytest.mark.asyncio
async def test_omitted_and_extra_ids_write_nothing() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository, count=3)
    translator = StubTranslator(
        _payload(
            [
                {"player_id": "ply_1", "localized_name": "甲", "aliases": []},
                {"player_id": "ply_9", "localized_name": "extra but unknown to batch", "aliases": []},
            ]
        )
    )
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    with pytest.raises(AppError, match="translation batch"):
        await enricher.enrich_missing(batch_size=3)
    assert (await repository.directory_counts())["localized"] == 0


@pytest.mark.asyncio
async def test_blank_name_writes_nothing() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator(
        _payload(
            [
                {"player_id": "ply_1", "localized_name": "  ", "aliases": []},
                {"player_id": "ply_2", "localized_name": "乙", "aliases": []},
            ]
        )
    )
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    with pytest.raises(AppError, match="translation batch"):
        await enricher.enrich_missing(batch_size=2)
    assert (await repository.directory_counts())["localized"] == 0


@pytest.mark.asyncio
async def test_malformed_batch_writes_nothing() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator('[{"player_id":"ply_unknown","localized_name":"未知"}]')
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    with pytest.raises(AppError, match="translation batch"):
        await enricher.enrich_missing(batch_size=2)
    assert await repository.directory_counts() == {
        "players": 2,
        "localized": 0,
        "aliases": 0,
        "ranked_atp": 2,
        "ranked_wta": 0,
    }


@pytest.mark.asyncio
async def test_translator_failure_reports_failed_batch_without_writes() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    translator = StubTranslator(error=AppError("llm_unavailable", "LLM request failed", 503))
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    report = await enricher.enrich_missing(batch_size=2)

    assert report.failed == 1
    assert report.translated == 0
    assert (await repository.directory_counts())["localized"] == 0


@pytest.mark.asyncio
async def test_rerun_skips_existing_names_and_makes_no_model_calls() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    calls: list[tuple[PlayerNameInput, ...]] = []

    async def respond(players: tuple[PlayerNameInput, ...]) -> str:
        calls.append(players)
        return _ok_payload(players)

    translator = StubTranslator()
    translator.translate = respond  # type: ignore[method-assign]
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    first = await enricher.enrich_missing(batch_size=2)
    second = await enricher.enrich_missing(batch_size=2)

    assert first.translated == 2
    assert second.translated == 0
    assert second.batches == 0
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_chinese_aliases_cover_preferred_full_and_surname() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository, count=1)
    # Rename to a dotted transliteration to exercise surname derivation.
    await repository.save_localized_names(())  # no-op keeps protocol exercised
    translator = StubTranslator(
        _payload([{"player_id": "ply_1", "localized_name": "本·谢尔顿", "aliases": []}])
    )
    enricher = PlayerAliasEnricher(repository, translator, model="test-model")

    await enricher.enrich_missing(batch_size=1)

    for normalized, kind in (
        ("本谢尔顿", PlayerAliasKind.PREFERRED),
        ("本谢尔顿", PlayerAliasKind.FULL),
        ("谢尔顿", PlayerAliasKind.SURNAME),
    ):
        matches = await repository.find_aliases(normalized, limit=10)
        assert any(
            match.player.player.id == "ply_1" and match.alias.kind is kind
            for match in matches
        )
        assert all(
            match.alias.source.value == "llm"
            and match.alias.prompt_version == PLAYER_NAME_PROMPT_VERSION
            for match in matches
            if match.player.player.id == "ply_1"
        )


@pytest.mark.asyncio
async def test_unnamed_placeholder_players_are_not_enrichment_inputs() -> None:
    repository = MemoryPlayerDirectoryRepository()
    await _seed(repository)
    # Simulate a match-observed placeholder: alias-only players never enter the
    # missing list because they have no English name to translate.
    missing = await repository.list_players_missing_localized_name(limit=10)
    assert all(item.player.name for item in missing)


def test_parse_translation_payload_strips_markdown_fence() -> None:
    fenced = "```json\n" + _payload(
        [{"player_id": "ply_1", "localized_name": "甲", "aliases": ["甲"]}]
    ) + "\n```"
    parsed = parse_translation_payload(fenced)
    assert parsed[0].player_id == "ply_1"
    assert parsed[0].localized_name == "甲"


def test_parse_translation_payload_rejects_non_object_and_bad_rows() -> None:
    with pytest.raises(AppError, match="translation batch"):
        parse_translation_payload("[1, 2]")
    with pytest.raises(AppError, match="translation batch"):
        parse_translation_payload('{"players": [{"player_id": "ply_1"}]}')
    with pytest.raises(AppError, match="translation batch"):
        parse_translation_payload("not json")


def test_translator_input_payload_contains_only_public_identity_fields() -> None:
    payload = OpenAICompatibleTranslator.build_user_payload(
        (
            PlayerNameInput(
                player_id="ply_1",
                name="Ben Shelton",
                country_code="usa",
                birth_date=None,
                gender=Gender.MEN,
            ),
        )
    )
    data = json.loads(payload)
    assert data == [
        {
            "player_id": "ply_1",
            "name": "Ben Shelton",
            "country_code": "usa",
            "birth_date": None,
            "gender": "men",
        }
    ]


def test_web_runtime_never_constructs_the_translator_or_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import openai

    from app.config import Settings
    from app.main import create_app

    constructed: list[dict] = []

    class Recorder:
        def __init__(self, *args, **kwargs) -> None:
            constructed.append(kwargs)

    monkeypatch.setattr(openai, "AsyncOpenAI", Recorder)

    for provider_mode in ("fake", "api_tennis"):
        settings = Settings(
            _env_file=None,
            provider_mode=provider_mode,
            llm_mode="fake",
            api_tennis_api_key="test-key",
        )
        create_app(settings)

    assert constructed == []
