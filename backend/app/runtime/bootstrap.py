"""All-or-nothing local runtime `init` sequence (T75).

Fixed order: migrations → ranking sync → known-player alias sync →
canonical catalog sync → aliases for newly cataloged players → one-shot
offline enrichment of missing Chinese names → aggregate init record → init
marker. The marker is written last and only after every required step
succeeded; provider or enrichment failures raise typed `AppError`s and leave
previously persisted rows and any prior successful marker untouched. Only
aggregate counts are recorded — never provider payloads, external
identifiers or secrets.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from app.errors import AppError
from app.players.enrichment import PlayerAliasEnricher
from app.players.sync import DirectorySyncReport, PlayerDirectorySync
from app.runtime.catalog import CatalogSynchronizer, CatalogSyncResult
from app.runtime.models import RuntimeInitRecord

ENRICHMENT_BATCH_SIZE = 25


class MigrationRunner(Protocol):
    """Injected schema migration runner (the Alembic adapter is wired by the
    local launcher in a later task; unit tests use a recording fake).

    `upgrade_head` applies every pending migration and returns the resulting
    schema revision identifier.
    """

    async def upgrade_head(self) -> str:
        raise NotImplementedError


class RuntimeInitState(Protocol):
    """Narrow init-marker view of `RuntimeStateRepository`, which satisfies
    this protocol structurally."""

    async def is_initialized(self) -> bool:
        raise NotImplementedError

    async def mark_initialized(self, record: RuntimeInitRecord) -> None:
        raise NotImplementedError


class RuntimeBootstrapper:
    def __init__(
        self,
        *,
        migrations: MigrationRunner,
        directory: PlayerDirectorySync,
        catalog: CatalogSynchronizer,
        enricher: PlayerAliasEnricher,
        state: RuntimeInitState,
        now: Callable[[], datetime],
    ) -> None:
        self._migrations = migrations
        self._directory = directory
        self._catalog = catalog
        self._enricher = enricher
        self.state = state
        self._now = now

    async def initialize(self) -> RuntimeInitRecord:
        """Run the full init sequence; write the marker only on full success.

        No step failure is swallowed: a failing ranking sync or missing-name
        enrichment aborts with a typed `AppError` before the marker exists,
        while rows already persisted by earlier successful steps (rankings,
        aliases, catalog) are preserved for the next run.
        """
        migration_revision = await self._migrations.upgrade_head()
        rankings = await self._directory.sync_rankings()
        if rankings.failed:
            raise AppError("provider_unavailable", "Ranking initialization failed", 503)
        await self._directory.sync_known_player_aliases()
        catalog = await self._catalog.sync()
        await self._directory.sync_player_aliases(catalog.newly_seen_player_ids)
        enrichment = await self._enricher.enrich_missing(
            batch_size=ENRICHMENT_BATCH_SIZE
        )
        if enrichment.failed:
            raise AppError(
                "provider_unavailable", "Chinese alias initialization failed", 503
            )
        record = self._build_record(migration_revision, rankings, catalog)
        await self.state.mark_initialized(record)
        return record

    def _build_record(
        self,
        migration_revision: str,
        rankings: DirectorySyncReport,
        catalog: CatalogSyncResult,
    ) -> RuntimeInitRecord:
        """Aggregate counts only: players seen by the ranking sync and
        deduplicated catalog matches; never provider payloads or external
        identifiers."""
        return RuntimeInitRecord(
            completed_at=self._now(),
            migration_revision=migration_revision,
            player_count=rankings.discovered + rankings.updated,
            match_count=catalog.live_matches + catalog.upcoming_matches,
        )
