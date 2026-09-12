"""Deterministic PlayerResolver acceptance tests (memory directory, no network)."""

from datetime import datetime, timezone

import pytest

from app.domain import Player
from app.errors import AppError
from app.players.models import (
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
    RankingEntry,
    RankingMovement,
    Tour,
)
from app.players.normalization import derive_english_aliases
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.resolver import PlayerResolutionStatus, PlayerResolver

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)

SHELTON_ID = "ply_shelton"
ZHENG_ID = "ply_zheng"
DJOKOVIC_ID = "ply_djokovic"


def _entry(player_id: str, name: str, rank: int | None, tour: Tour = Tour.ATP) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, country_code="usa", ranking=rank),
        tour=tour,
        rank=rank or 9999,
        points=100,
        movement=RankingMovement.SAME,
        ranking_date=NOW.date(),
        fetched_at=NOW,
    )


def _zh_aliases(player_id: str, localized: str) -> tuple[PlayerAlias, ...]:
    from app.players.enrichment import derive_chinese_aliases

    return derive_chinese_aliases(player_id, localized, model="test-model")


@pytest.fixture()
async def repository() -> MemoryPlayerDirectoryRepository:
    repo = MemoryPlayerDirectoryRepository()
    await repo.save_ranking_snapshot(
        (
            _entry(SHELTON_ID, "Ben Shelton", 5),
            _entry(ZHENG_ID, "Qinwen Zheng", 5, Tour.WTA),
            _entry(DJOKOVIC_ID, "Novak Djokovic", 4),
            _entry("ply_wang_xinyu", "Xinyu Wang", 25, Tour.WTA),
            _entry("ply_wang_xiyu", "Xiyu Wang", 50, Tour.WTA),
            _entry("ply_lehecka", "Lehečka Jiří", 30),
        )
    )
    for directory_player in await repo.list_players_for_alias_sync(limit=100):
        await repo.upsert_aliases(derive_english_aliases(directory_player))
    await repo.upsert_aliases(_zh_aliases(SHELTON_ID, "本·谢尔顿"))
    await repo.upsert_aliases(_zh_aliases(ZHENG_ID, "郑钦文"))
    await repo.upsert_aliases(_zh_aliases(DJOKOVIC_ID, "诺瓦克·德约科维奇"))
    await repo.upsert_aliases(_zh_aliases("ply_wang_xinyu", "王欣瑜"))
    await repo.upsert_aliases(_zh_aliases("ply_wang_xiyu", "王曦雨"))
    return repo


@pytest.fixture()
def resolver(repository: MemoryPlayerDirectoryRepository) -> PlayerResolver:
    return PlayerResolver(repository)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("Ben Shelton", SHELTON_ID),
        ("Shelton", SHELTON_ID),
        ("B. Shelton", SHELTON_ID),
        ("本·谢尔顿", SHELTON_ID),
        ("谢尔顿", SHELTON_ID),
        ("Qinwen Zheng", ZHENG_ID),
        ("Zheng Qinwen", ZHENG_ID),
        ("Q. Zheng", ZHENG_ID),
        ("郑钦文", ZHENG_ID),
        ("Novak Djokovic", DJOKOVIC_ID),
        ("Djokovic", DJOKOVIC_ID),
        ("N. Djokovic", DJOKOVIC_ID),
        ("德约科维奇", DJOKOVIC_ID),
    ],
)
async def test_approved_alias_groups_resolve_to_one_internal_id(
    resolver: PlayerResolver, query: str, expected_id: str
) -> None:
    result = await resolver.resolve(query)
    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player is not None
    assert result.player.id == expected_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    ["  ben   shelton  ", "BEN-SHELTON", "ben shelton.", "Shelton Ben"],
)
async def test_normalization_variants_resolve(
    resolver: PlayerResolver, query: str
) -> None:
    result = await resolver.resolve(query)
    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player is not None
    assert result.player.id == SHELTON_ID


@pytest.mark.asyncio
async def test_accented_and_unaccented_forms_resolve(
    resolver: PlayerResolver,
) -> None:
    for query in ("Lehečka Jiří", "lehecka jiri"):
        result = await resolver.resolve(query)
        assert result.status is PlayerResolutionStatus.RESOLVED
        assert result.player is not None
        assert result.player.id == "ply_lehecka"


@pytest.mark.asyncio
async def test_ambiguous_surname_returns_candidates(resolver: PlayerResolver) -> None:
    result = await resolver.resolve("Wang")

    assert result.status is PlayerResolutionStatus.AMBIGUOUS
    assert result.player is None
    assert {candidate.player.id for candidate in result.candidates} == {
        "ply_wang_xinyu",
        "ply_wang_xiyu",
    }


@pytest.mark.asyncio
async def test_match_context_resolves_unique_participant(
    resolver: PlayerResolver,
) -> None:
    result = await resolver.resolve("Wang", context_player_ids=("ply_wang_xiyu",))

    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player is not None
    assert result.player.id == "ply_wang_xiyu"


@pytest.mark.asyncio
async def test_match_context_with_no_participant_stays_ambiguous(
    resolver: PlayerResolver,
) -> None:
    result = await resolver.resolve("Wang", context_player_ids=("ply_someone_else",))
    assert result.status is PlayerResolutionStatus.AMBIGUOUS


@pytest.mark.asyncio
async def test_empty_query_is_input_error(resolver: PlayerResolver) -> None:
    with pytest.raises(AppError) as failure:
        await resolver.resolve("   ")
    assert failure.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_unknown_query_is_recoverable_not_found(
    resolver: PlayerResolver,
) -> None:
    result = await resolver.resolve("zzz nobody")
    assert result.status is PlayerResolutionStatus.NOT_FOUND
    assert result.player is None
    assert result.candidates == ()


@pytest.mark.asyncio
async def test_internal_id_lookup_resolves_directly(
    resolver: PlayerResolver,
) -> None:
    result = await resolver.resolve(SHELTON_ID)
    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player is not None
    assert result.player.id == SHELTON_ID


@pytest.mark.asyncio
async def test_obvious_short_alias_candidate_resolves_over_outside_top200() -> None:
    repo = MemoryPlayerDirectoryRepository()
    await repo.save_ranking_snapshot(
        (
            _entry(SHELTON_ID, "Ben Shelton", 9),
            _entry("ply_sheldon_max", "Max Sheldon", 1339),
            _entry("ply_sheldon_mitch", "Mitchell Sheldon", 1344),
        )
    )
    for player_id in (SHELTON_ID, "ply_sheldon_max", "ply_sheldon_mitch"):
        directory_player = await repo.get_player(player_id)
        assert directory_player is not None
        await repo.upsert_aliases(derive_english_aliases(directory_player))
    await repo.upsert_aliases(_zh_aliases(SHELTON_ID, "本·谢尔顿"))
    await repo.upsert_aliases(_zh_aliases("ply_sheldon_max", "马克·谢尔顿"))
    await repo.upsert_aliases(_zh_aliases("ply_sheldon_mitch", "米切尔·谢尔顿"))
    resolver = PlayerResolver(repo)

    result = await resolver.resolve("谢尔顿")
    assert result.status is PlayerResolutionStatus.RESOLVED
    assert result.player is not None
    assert result.player.id == SHELTON_ID


@pytest.mark.asyncio
async def test_same_window_surname_conflict_stays_ambiguous() -> None:
    repo = MemoryPlayerDirectoryRepository()
    await repo.save_ranking_snapshot(
        (
            _entry("ply_wang_a", "Xinyu Wang", 25, Tour.WTA),
            _entry("ply_wang_b", "Xiyu Wang", 50, Tour.WTA),
        )
    )
    for player_id in ("ply_wang_a", "ply_wang_b"):
        directory_player = await repo.get_player(player_id)
        assert directory_player is not None
        await repo.upsert_aliases(derive_english_aliases(directory_player))
        await repo.upsert_aliases(_zh_aliases(player_id, "王"))
    resolver = PlayerResolver(repo)

    result = await resolver.resolve("王")
    assert result.status is PlayerResolutionStatus.AMBIGUOUS
