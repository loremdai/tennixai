"""PlayerDirectorySync determinism, idempotency, and failure-preservation tests."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.domain import Player
from app.errors import AppError
from app.players.models import PlayerAliasSource, RankingEntry, RankingMovement, Tour
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.sync import DirectorySeeder, DirectorySyncReport, PlayerDirectorySync

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


class AliasSpyRepository(MemoryPlayerDirectoryRepository):
    """Records which player IDs are queried and any full-directory scans."""

    def __init__(self) -> None:
        super().__init__()
        self.requested_player_ids: list[str] = []
        self.directory_scan_calls = 0

    async def get_player(self, player_id: str):
        self.requested_player_ids.append(player_id)
        return await super().get_player(player_id)

    async def list_players_for_alias_sync(self, *, limit: int, after_id: str | None = None):
        self.directory_scan_calls += 1
        return await super().list_players_for_alias_sync(limit=limit, after_id=after_id)


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
async def test_directory_seeder_concurrent_ensure_waits_for_the_active_seed() -> None:
    class BlockingSync:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls: list[str] = []

        async def sync_rankings(self) -> None:
            self.calls.append("rankings")
            self.started.set()
            await self.release.wait()

        async def sync_known_player_aliases(self) -> None:
            self.calls.append("aliases")

    sync = BlockingSync()
    seeder = DirectorySeeder(sync)  # type: ignore[arg-type]
    first = asyncio.create_task(seeder.ensure())
    await sync.started.wait()
    second = asyncio.create_task(seeder.ensure())
    await asyncio.sleep(0)
    second_waited = not second.done()

    sync.release.set()
    await asyncio.gather(first, second)

    assert second_waited
    assert sync.calls == ["rankings", "aliases"]


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


@pytest.mark.asyncio
async def test_empty_standings_response_is_not_fresh_success() -> None:
    repository = SpyRepository()
    first = PlayerDirectorySync(
        StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW
    )
    await first.sync_rankings()

    empty = PlayerDirectorySync(
        StubCatalog(atp=(), wta=()), repository, now=lambda: NOW
    )
    report = await empty.sync_rankings()

    assert report.failed == 2
    assert repository.prune_calls == 1
    latest, total = await repository.get_rankings(
        Tour.WTA, page=1, page_size=50, country_code=None
    )
    assert total == 1
    assert latest[0].player.id == "ply_zheng"

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


@pytest.mark.asyncio
async def test_sync_player_aliases_queries_only_given_ids_without_llm() -> None:
    repository = AliasSpyRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()
    # Isolate the narrow path from ranking-sync's own directory reads.
    repository.requested_player_ids.clear()

    report = await sync.sync_player_aliases(["ply_ben", "ply_zheng"])

    assert report.aliases_inserted > 0
    assert report.failed == 0
    # Only the given IDs are queried; no full-directory alias scan runs.
    assert repository.requested_player_ids == ["ply_ben", "ply_zheng"]
    assert repository.directory_scan_calls == 0
    counts = await repository.directory_counts()
    assert counts["aliases"] == report.aliases_inserted


@pytest.mark.asyncio
async def test_sync_player_aliases_is_idempotent() -> None:
    repository = MemoryPlayerDirectoryRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()

    first = await sync.sync_player_aliases(["ply_ben", "ply_bryan", "ply_zheng"])
    assert first.aliases_inserted > 0

    second = await sync.sync_player_aliases(["ply_ben", "ply_bryan", "ply_zheng"])
    assert second.aliases_inserted == 0


@pytest.mark.asyncio
async def test_sync_player_aliases_uses_derived_english_aliases_only() -> None:
    repository = MemoryPlayerDirectoryRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()

    await sync.sync_player_aliases(["ply_ben"])

    matches = await repository.find_aliases("shelton", limit=10)
    ben = [match for match in matches if match.player.player.id == "ply_ben"]
    assert ben
    assert all(match.alias.source is PlayerAliasSource.DERIVED for match in ben)
    # A narrow ID sync never touches the sibling player it was not given.
    assert all(match.player.player.id != "ply_bryan" for match in matches)


@pytest.mark.asyncio
async def test_sync_player_aliases_empty_ids_is_a_noop() -> None:
    repository = AliasSpyRepository()
    sync = PlayerDirectorySync(StubCatalog(atp=ATP, wta=WTA), repository, now=lambda: NOW)
    await sync.sync_rankings()
    repository.requested_player_ids.clear()

    report = await sync.sync_player_aliases([])

    assert report.aliases_inserted == 0
    assert repository.requested_player_ids == []
    assert repository.directory_scan_calls == 0
