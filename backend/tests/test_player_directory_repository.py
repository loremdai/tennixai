"""PlayerDirectoryRepository contract tests (deterministic memory implementation)."""

from datetime import datetime, timezone

import pytest

from app.domain import Gender, Player
from app.errors import AppError
from app.players.models import (
    DirectoryPlayer,
    LocalizedNameUpdate,
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
    RankingEntry,
    RankingMovement,
    Tour,
)
from app.players.repository import MemoryPlayerDirectoryRepository

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


def entry(
    player_id: str,
    name: str,
    tour: Tour,
    rank: int,
    *,
    country: str | None = "ita",
    points: int = 100,
    fetched: datetime = NOW,
) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, country_code=country, ranking=rank),
        tour=tour,
        rank=rank,
        points=points,
        movement=RankingMovement.SAME,
        ranking_date=fetched.date(),
        fetched_at=fetched,
    )


def alias(
    player_id: str,
    normalized: str,
    *,
    kind: PlayerAliasKind = PlayerAliasKind.FULL,
    locale: str = "en",
    display: str | None = None,
) -> PlayerAlias:
    return PlayerAlias(
        player_id=player_id,
        locale=locale,
        alias=display or normalized,
        normalized_alias=normalized,
        kind=kind,
        source=PlayerAliasSource.DERIVED,
    )


@pytest.fixture()
def repository() -> MemoryPlayerDirectoryRepository:
    return MemoryPlayerDirectoryRepository()


@pytest.mark.asyncio
async def test_save_ranking_snapshot_upserts_players_and_latest_snapshot_wins(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    older = NOW.replace(day=5)
    await repository.save_ranking_snapshot(
        (
            entry("ply_a", "Alpha", Tour.ATP, 1, fetched=older),
            entry("ply_b", "Beta", Tour.ATP, 2, fetched=older),
        )
    )
    await repository.save_ranking_snapshot(
        (
            entry("ply_c", "Gamma", Tour.ATP, 1),
            entry("ply_a", "Alpha Renamed", Tour.ATP, 2),
        )
    )

    entries, total = await repository.get_rankings(Tour.ATP, page=1, page_size=50, country_code=None)
    assert total == 2
    assert [item.rank for item in entries] == [1, 2]
    assert [item.player.id for item in entries] == ["ply_c", "ply_a"]
    assert entries[1].player.name == "Alpha Renamed"

    player = await repository.get_player("ply_a")
    assert player is not None
    assert player.player.name == "Alpha Renamed"
    assert player.gender is Gender.UNKNOWN


@pytest.mark.asyncio
async def test_get_rankings_filters_country_and_paginates(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    snapshot = tuple(
        entry(
            f"ply_{index:03d}",
            f"Player {index}",
            Tour.ATP,
            index,
            country="chn" if index % 2 == 0 else "ita",
        )
        for index in range(1, 121)
    )
    await repository.save_ranking_snapshot(snapshot)

    chinese, total = await repository.get_rankings(Tour.ATP, page=1, page_size=50, country_code="chn")
    assert total == 60
    assert len(chinese) == 50
    assert all(item.player.country_code == "chn" for item in chinese)

    page3, total = await repository.get_rankings(Tour.ATP, page=3, page_size=50, country_code=None)
    assert total == 120
    assert [item.rank for item in page3][:3] == [101, 102, 103]


@pytest.mark.asyncio
async def test_upsert_aliases_is_idempotent(repository: MemoryPlayerDirectoryRepository) -> None:
    await repository.save_ranking_snapshot((entry("ply_a", "Alpha", Tour.ATP, 1),))

    first = await repository.upsert_aliases((alias("ply_a", "alpha"),))
    second = await repository.upsert_aliases((alias("ply_a", "alpha"),))

    assert first == 1
    assert second == 0
    matches = await repository.find_aliases("alpha", limit=10)
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_same_normalized_alias_can_return_two_players(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.save_ranking_snapshot(
        (
            entry("ply_a", "Alpha Wang", Tour.ATP, 10),
            entry("ply_b", "Beta Wang", Tour.WTA, 20),
        )
    )
    await repository.upsert_aliases(
        (alias("ply_a", "wang", kind=PlayerAliasKind.SURNAME, locale="zh-Hans", display="王"),)
    )
    await repository.upsert_aliases(
        (alias("ply_b", "wang", kind=PlayerAliasKind.SURNAME, locale="zh-Hans", display="王"),)
    )

    matches = await repository.find_aliases("wang", limit=10)
    assert {item.player.player.id for item in matches} == {"ply_a", "ply_b"}
    ranks = {item.player.player.id: item.current_rank for item in matches}
    assert ranks == {"ply_a": 10, "ply_b": 20}


@pytest.mark.asyncio
async def test_find_aliases_orders_by_kind_then_rank_then_id(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.save_ranking_snapshot(
        (
            entry("ply_r9", "Nine", Tour.ATP, 9),
            entry("ply_r5", "Five", Tour.ATP, 5),
            entry("ply_r50", "Fifty", Tour.ATP, 50),
            entry("ply_r7", "Seven", Tour.ATP, 7),
        )
    )
    await repository.upsert_aliases(
        (
            alias("ply_r50", "shared", kind=PlayerAliasKind.SURNAME),
            alias("ply_r5", "shared", kind=PlayerAliasKind.FULL),
            alias("ply_r7", "shared", kind=PlayerAliasKind.FULL),
            alias("ply_r9", "shared", kind=PlayerAliasKind.PREFERRED),
        )
    )

    matches = await repository.find_aliases("shared", limit=10)
    # preferred → full (rank order) → surname
    assert [item.player.player.id for item in matches] == [
        "ply_r9",
        "ply_r5",
        "ply_r7",
        "ply_r50",
    ]


@pytest.mark.asyncio
async def test_save_localized_names_updates_whole_batch_or_nothing(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.save_ranking_snapshot(
        (
            entry("ply_a", "Alpha", Tour.ATP, 1),
            entry("ply_b", "Beta", Tour.ATP, 2),
        )
    )

    written = await repository.save_localized_names(
        (
            LocalizedNameUpdate(
                player_id="ply_a",
                localized_name="阿尔法",
                aliases=(alias("ply_a", "阿尔法", locale="zh-Hans", kind=PlayerAliasKind.PREFERRED),),
            ),
        )
    )
    assert written == 1
    player = await repository.get_player("ply_a")
    assert player is not None
    assert player.player.localized_name == "阿尔法"

    with pytest.raises(AppError):
        await repository.save_localized_names(
            (
                LocalizedNameUpdate(player_id="ply_b", localized_name="贝塔", aliases=()),
                LocalizedNameUpdate(player_id="ply_missing", localized_name="不存在", aliases=()),
            )
        )
    untouched = await repository.get_player("ply_b")
    assert untouched is not None
    assert untouched.player.localized_name is None


@pytest.mark.asyncio
async def test_missing_localized_name_listing_and_counts(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.save_ranking_snapshot(
        (
            entry("ply_a", "Alpha", Tour.ATP, 1),
            entry("ply_b", "Beta", Tour.ATP, 2),
            entry("ply_w", "Wta", Tour.WTA, 1),
        )
    )

    missing = await repository.list_players_missing_localized_name(limit=10)
    assert [item.player.id for item in missing] == ["ply_a", "ply_b", "ply_w"]

    await repository.save_localized_names(
        (LocalizedNameUpdate(player_id="ply_a", localized_name="阿尔法", aliases=()),)
    )
    counts = await repository.directory_counts()
    assert counts == {
        "players": 3,
        "localized": 1,
        "aliases": 0,
        "ranked_atp": 2,
        "ranked_wta": 1,
    }


@pytest.mark.asyncio
async def test_alias_sync_cursor_pages_through_players(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.save_ranking_snapshot(
        (
            entry("ply_a", "Alpha", Tour.ATP, 1),
            entry("ply_b", "Beta", Tour.ATP, 2),
            entry("ply_c", "Gamma", Tour.ATP, 3),
        )
    )

    first = await repository.list_players_for_alias_sync(limit=2)
    assert [item.player.id for item in first] == ["ply_a", "ply_b"]
    second = await repository.list_players_for_alias_sync(limit=2, after_id=first[-1].player.id)
    assert [item.player.id for item in second] == ["ply_c"]


@pytest.mark.asyncio
async def test_prune_ranking_snapshots_keeps_bounded_history(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    for day in range(1, 12):
        fetched = NOW.replace(day=day)
        await repository.save_ranking_snapshot(
            (entry("ply_a", "Alpha", Tour.ATP, 1, fetched=fetched),)
        )

    removed = await repository.prune_ranking_snapshots(keep_per_tour=8)
    assert removed == 3

    entries, total = await repository.get_rankings(Tour.ATP, page=1, page_size=50, country_code=None)
    assert total == 1
    assert entries[0].ranking_date == NOW.replace(day=11).date()


@pytest.mark.asyncio
async def test_directory_player_keeps_identity_without_ranking(
    repository: MemoryPlayerDirectoryRepository,
) -> None:
    await repository.upsert_aliases(
        (alias("ply_ghost", "ghost", kind=PlayerAliasKind.FULL),)
    )
    # Alias-only players are not directory members until observed.
    assert await repository.get_player("ply_ghost") is None
    matches = await repository.find_aliases("ghost", limit=5)
    assert matches == ()
