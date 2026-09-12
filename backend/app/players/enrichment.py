"""Offline Chinese-name enrichment with strict batch validation.

The translator calls the configured OpenAI-compatible endpoint with public
identity fields only. Every returned batch must match the input IDs exactly;
any unknown, duplicate, omitted, extra or blank entry aborts the batch with
zero writes. The web runtime never imports this module.
"""

import asyncio
import json
import re
from datetime import date
from typing import Protocol

from pydantic import Field, ValidationError

from app.domain import FrozenModel, Gender
from app.errors import AppError
from app.players.models import (
    LocalizedNameUpdate,
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
)
from app.players.normalization import normalize_player_name
from app.players.repository import PlayerDirectoryRepository

PLAYER_NAME_PROMPT_VERSION = "zh-Hans-player-name-v1"

_SYSTEM_INSTRUCTION = (
    "You translate tennis player display names into Simplified Chinese. "
    'Return ONLY a JSON object shaped as {"players": [{"player_id": string, '
    '"localized_name": string, "aliases": [string]}]} with exactly one entry '
    "per input player_id, using the widely accepted Chinese media name when "
    "known. Never invent player IDs, merge players, or change English names."
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


class PlayerNameInput(FrozenModel):
    player_id: str
    name: str
    country_code: str | None = None
    birth_date: date | None = None
    gender: Gender = Gender.UNKNOWN


class PlayerNameTranslation(FrozenModel):
    player_id: str
    localized_name: str = Field(min_length=1, max_length=80)
    aliases: tuple[str, ...] = ()


class EnrichmentReport(FrozenModel):
    translated: int = 0
    skipped: int = 0
    failed: int = 0
    batches: int = 0


class PlayerNameTranslator(Protocol):
    async def translate(self, players: tuple[PlayerNameInput, ...]) -> str:
        raise NotImplementedError


def parse_translation_payload(text: str) -> tuple[PlayerNameTranslation, ...]:
    """Strict structural validation; failures are typed, never guessed."""
    stripped = (text or "").strip()
    fence = _FENCE.fullmatch(stripped)
    if fence is not None:
        stripped = fence.group(1)
    try:
        data = json.loads(stripped)
    except ValueError as error:
        raise AppError(
            "invalid_translation_batch", "translation batch validation failed", 502
        ) from error
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise AppError(
            "invalid_translation_batch", "translation batch validation failed", 502
        )
    try:
        return tuple(
            PlayerNameTranslation.model_validate(row) for row in data["players"]
        )
    except ValidationError as error:
        raise AppError(
            "invalid_translation_batch", "translation batch validation failed", 502
        ) from error


class OpenAICompatibleTranslator:
    """Thin HTTP adapter; parsing and identity validation live in the enricher."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 45.0,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds
        )
        self._model = model
        self._timeout_seconds = timeout_seconds
        self.request_count = 0

    @staticmethod
    def build_user_payload(players: tuple[PlayerNameInput, ...]) -> str:
        return json.dumps(
            [player.model_dump(mode="json") for player in players],
            ensure_ascii=False,
        )

    async def translate(self, players: tuple[PlayerNameInput, ...]) -> str:
        from openai import OpenAIError

        self.request_count += 1
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_INSTRUCTION},
                        {"role": "user", "content": self.build_user_payload(players)},
                    ],
                    extra_body={"enable_thinking": False},
                )
        except (OpenAIError, TimeoutError) as error:
            raise AppError("llm_unavailable", "LLM request failed", 503) from error
        return response.choices[0].message.content or ""


def derive_chinese_aliases(
    player_id: str, localized_name: str, *, model: str
) -> tuple[PlayerAlias, ...]:
    """Preferred full name, dot-free form and common surname (spec §7.2)."""
    normalized = normalize_player_name(localized_name)
    aliases = [
        PlayerAlias(
            player_id=player_id,
            locale="zh-Hans",
            alias=localized_name,
            normalized_alias=normalized,
            kind=PlayerAliasKind.PREFERRED,
            source=PlayerAliasSource.LLM,
            model=model,
            prompt_version=PLAYER_NAME_PROMPT_VERSION,
        ),
        PlayerAlias(
            player_id=player_id,
            locale="zh-Hans",
            alias=normalized,
            normalized_alias=normalized,
            kind=PlayerAliasKind.FULL,
            source=PlayerAliasSource.LLM,
            model=model,
            prompt_version=PLAYER_NAME_PROMPT_VERSION,
        ),
    ]
    if "·" in localized_name:
        surname = localized_name.rsplit("·", 1)[-1].strip()
    elif len(normalized) >= 2:
        surname = normalized[0]
    else:
        surname = ""
    if surname:
        aliases.append(
            PlayerAlias(
                player_id=player_id,
                locale="zh-Hans",
                alias=surname,
                normalized_alias=normalize_player_name(surname),
                kind=PlayerAliasKind.SURNAME,
                source=PlayerAliasSource.LLM,
                model=model,
                prompt_version=PLAYER_NAME_PROMPT_VERSION,
            )
        )
    return tuple(aliases)


class PlayerAliasEnricher:
    def __init__(
        self,
        repository: PlayerDirectoryRepository,
        translator: PlayerNameTranslator,
        *,
        model: str,
    ) -> None:
        self._repository = repository
        self._translator = translator
        self._model = model

    async def enrich_missing(
        self, *, batch_size: int = 25, max_batches: int | None = None
    ) -> EnrichmentReport:
        translated = 0
        skipped = 0
        failed = 0
        batches = 0
        while max_batches is None or batches < max_batches:
            missing = await self._repository.list_players_missing_localized_name(
                limit=batch_size
            )
            if not missing:
                break
            inputs = tuple(
                PlayerNameInput(
                    player_id=player.player.id,
                    name=player.player.name,
                    country_code=player.player.country_code,
                    birth_date=player.birth_date,
                    gender=player.gender,
                )
                for player in missing
            )
            batches += 1
            try:
                raw = await self._translator.translate(inputs)
                translations = parse_translation_payload(raw)
                _validate_batch_identity(inputs, translations)
            except AppError as error:
                if error.code == "llm_unavailable":
                    failed += 1
                    break
                raise
            updates = tuple(
                LocalizedNameUpdate(
                    player_id=translation.player_id,
                    localized_name=translation.localized_name.strip(),
                    aliases=derive_chinese_aliases(
                        translation.player_id,
                        translation.localized_name.strip(),
                        model=self._model,
                    ),
                )
                for translation in translations
            )
            translated += await self._repository.save_localized_names(updates)
        return EnrichmentReport(
            translated=translated, skipped=skipped, failed=failed, batches=batches
        )


def _validate_batch_identity(
    inputs: tuple[PlayerNameInput, ...],
    translations: tuple[PlayerNameTranslation, ...],
) -> None:
    expected = sorted(player.player_id for player in inputs)
    got = [translation.player_id for translation in translations]
    if sorted(got) != expected or len(set(got)) != len(got):
        raise AppError(
            "invalid_translation_batch",
            "translation batch validation failed",
            502,
            {"expected": expected, "returned": sorted(got)},
        )
    for translation in translations:
        if not translation.localized_name.strip():
            raise AppError(
                "invalid_translation_batch",
                "translation batch validation failed",
                502,
                {"player_id": translation.player_id},
            )
