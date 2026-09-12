"""PlayerDirectorySync determinism, idempotency, and failure-preservation tests."""

from datetime import datetime, timezone

import pytest

from app.domain import Player
from app.errors import AppError
from app.players.models import RankingEntry, RankingMovement, Tour
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.sync import DirectorySyncReport, PlayerDirectorySync

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


def entry(player_id: str, name: str, tour: Tour, rank: int) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, country_code="usa", ranking=rank),
        tour=tour,
        rank=rank,
        points=1000 - rank,
        movement=RankingMovement.SAME,
        ranking_date=NOW.date(),
        fetched_at=NOW,
    )


class StubCatalog:
    def __init__(
        self,
        atp: tuple[RankingEntry, ...] = (),
        wta: tuple[RankingEntry, ...] = (),
        wta_error: AppError | None = None,
    ) -> None:
        self.atp = atp
        self.wta = wta
        self.wta_error = wta_error
        self.calls: list[Tour] = []

    async def get_rankings(self, tour: Tour) -> tuple[RankingEntry, ...]:
        self.calls.append(tour)
        if tour is Tour.ATP:
            return self.atp
        if self.wta_error is not None:
            raise self.wta_error
        return self.wta


class SpyRepository(MemoryPlayerDirectoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.prune_calls = 0

    async def prune_ranking_snapshots(self, *, keep_per_tour: int = 8) -> int:
        self.prune_calls += 1
        return await super().prune_ranking_snapshots(keep_per_tour=keep_per_tour)


ATP = (
    entry("ply_ben", "Ben Shelton", Tour.ATP, 5),
    entry("ply_bryan", "Bryan Shelton", Tour.ATP, 301),
)
WTA = (entry("ply_zheng", "Qinwen Zheng", Tour.WTA, 5),)


@pytest.mark.asyncio
async def test_sync_rankings_discovers_then_updates_on_rerun() -> None:
    repository = MemoryPlayerDirectoryRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)

    first = await sync.sync_rankings()
    assert (first.discovered, first.updated, first.failed) == (3, 0, 0)

    second = await sync.sync_rankings()
    assert (second.discovered, second.updated, second.failed) == (0, 3, 0)


@pytest.mark.asyncio
async def test_sync_known_player_aliases_is_idempotent() -> None:
    repository = MemoryPlayerDirectoryRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()

    first = await sync.sync_known_player_aliases(batch_size=2)
    assert first.aliases_inserted > 0
    assert first.failed == 0

    second = await sync.sync_known_player_aliases(batch_size=2)
    assert second.aliases_inserted == 0

    matches = await repository.find_aliases("shelton", limit=10)
    assert {match.player.player.id for match in matches} == {"ply_ben", "ply_bryan"}


@pytest.mark.asyncio
async def test_tour_failure_keeps_previous_snapshot_and_skips_prune() -> None:
    repository = SpyRepository()
    healthy = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    first = await healthy.sync_rankings()
    assert first.failed == 0
    assert repository.prune_calls == 1

    failing = PlayerDirectorySync(
        StubCatalog(atp=ATP, wta_error=AppError("provider_unavailable", "boom", 503)),
        repository,
        now=lambda: NOW,
    )
    report = await failing.sync_rankings()
    assert report.failed == 1

    # The previous WTA snapshot survives the failed tour write.
    wta, total = await repository.get_rankings(Tour.WTA, page=1, page_size=50, country_code=None)
    assert total == 1
    assert wta[0].player.id == "ply_zheng"
    # Pruning only happens after both tours succeed.
    assert repository.prune_calls == 1


@pytest.mark.asyncio
async def test_sync_pages_through_known_players_in_batches() -> None:
    repository = MemoryPlayerDirectoryRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()

    report: DirectorySyncReport = await sync.sync_known_player_aliases(batch_size=2)
    counts = await repository.directory_counts()
    assert counts["aliases"] == report.aliases_inserted
    assert counts["aliases"] > 0
    # Every directory player received at least a full-name alias.
    for player_id in ("ply_ben", "ply_bryan", "ply_zheng"):
        player = await repository.get_player(player_id)
        assert player is not None
        from app.players.normalization import normalize_player_name

        matches = await repository.find_aliases(normalize_player_name(player.player.name), limit=5)
        assert any(match.player.player.id == player_id for match in matches)
