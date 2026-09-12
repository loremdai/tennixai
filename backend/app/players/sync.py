"""Explicit, repeatable player directory sync (no cron, queues, or daemons).

`sync_rankings` persists one atomic snapshot per tour; a failing tour keeps the
previous snapshot and is counted in `failed`. `sync_known_player_aliases`
pages through known singles players and derives deterministic English aliases.
"""

from collections.abc import Callable
from datetime import datetime

from app.errors import AppError
from app.players.models import Tour
from app.players.normalization import derive_english_aliases
from app.players.providers import PlayerCatalogProvider
from app.players.repository import PlayerDirectoryRepository
from app.domain import FrozenModel


class DirectorySyncReport(FrozenModel):
    discovered: int = 0
    updated: int = 0
    aliases_inserted: int = 0
    skipped: int = 0
    failed: int = 0


class DirectorySeeder:
    """One-shot directory bootstrap for in-memory (fake) app modes."""

    def __init__(self, sync: "PlayerDirectorySync") -> None:
        self._sync = sync
        self._done = False

    async def ensure(self) -> None:
        if self._done:
            return
        self._done = True
        await self._sync.sync_rankings()
        await self._sync.sync_known_player_aliases()


class PlayerDirectorySync:
    def __init__(
        self,
        provider: PlayerCatalogProvider,
        repository: PlayerDirectoryRepository,
        *,
        now: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._now = now

    async def sync_rankings(self) -> DirectorySyncReport:
        discovered = 0
        updated = 0
        skipped = 0
        failed = 0
        succeeded_tours = 0
        for tour in (Tour.ATP, Tour.WTA):
            try:
                entries = await self._provider.get_rankings(tour)
            except AppError:
                # Keep the last good snapshot for this tour; never replace it
                # with an empty one and never prune after a partial sync.
                failed += 1
                continue
            for entry in entries:
                existing = await self._repository.get_player(entry.player.id)
                if existing is None:
                    discovered += 1
                else:
                    updated += 1
            # Tied supplier ranks collapse to one snapshot row per rank.
            skipped += len(entries) - len(
                {(entry.tour, entry.ranking_date, entry.rank) for entry in entries}
            )
            await self._repository.save_ranking_snapshot(entries)
            succeeded_tours += 1
        if succeeded_tours == len(Tour):
            await self._repository.prune_ranking_snapshots(keep_per_tour=8)
        return DirectorySyncReport(
            discovered=discovered, updated=updated, skipped=skipped, failed=failed
        )

    async def sync_known_player_aliases(self, *, batch_size: int = 500) -> DirectorySyncReport:
        aliases_inserted = 0
        skipped = 0
        after_id: str | None = None
        while True:
            batch = await self._repository.list_players_for_alias_sync(
                limit=batch_size, after_id=after_id
            )
            if not batch:
                break
            for directory_player in batch:
                aliases = derive_english_aliases(directory_player)
                inserted = await self._repository.upsert_aliases(aliases)
                aliases_inserted += inserted
                skipped += len(aliases) - inserted
            after_id = batch[-1].player.id
            if len(batch) < batch_size:
                break
        return DirectorySyncReport(aliases_inserted=aliases_inserted, skipped=skipped)
