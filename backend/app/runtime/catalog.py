"""Canonical match catalog sync for the P4 local runtime (T75).

`CatalogSynchronizer` is the only writer of the canonical match catalog
during `init`: it queries the live and upcoming provider endpoints exactly
once per sync, deduplicates by internal match ID (the live row wins),
persists canonical `Match` rows through the catalog repository, and reports
aggregate counts plus the newly seen internal player IDs in sorted order.
Provider failures propagate as the typed `AppError` raised by the provider;
a failed sync writes nothing and never deletes previously persisted rows.
Only canonical data with internal IDs is handled here — provider payloads
and external identifiers never pass through this module.
"""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from pydantic import field_validator

from app.decision.worker import MatchTrackingInfo
from app.domain import FrozenModel, Match


class CatalogMatchSource(Protocol):
    """Structural match source; `ApiTennisProvider` satisfies it."""

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        raise NotImplementedError


class MatchCatalogStore(Protocol):
    """Structural catalog store; `MatchCatalogRepository` satisfies it."""

    async def upsert_matches(
        self, matches: Sequence[Match], *, observed_at: datetime
    ) -> set[str]:
        raise NotImplementedError

    async def get_match(self, match_id: str) -> Match | None:
        raise NotImplementedError


class CatalogSyncResult(FrozenModel):
    """Aggregate outcome of one catalog sync.

    Counts and internal player IDs only; never provider payloads, external
    identifiers or raw rows.
    """

    live_matches: int
    upcoming_matches: int
    newly_seen_player_ids: tuple[str, ...]
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_observed_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class CatalogSynchronizer:
    def __init__(
        self,
        provider: CatalogMatchSource,
        catalog: MatchCatalogStore,
        *,
        now: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._catalog = catalog
        self._now = now

    async def sync(self) -> CatalogSyncResult:
        """Fetch live and upcoming matches exactly once each and persist the
        deduplicated canonical rows in one upsert batch."""
        observed_at = self._now()
        live = await self._provider.get_live_matches()
        fixtures = await self._provider.get_fixtures()

        deduped: dict[str, Match] = {}
        for match in live:
            deduped[match.id] = match
        live_matches = len(deduped)
        upcoming_matches = 0
        for match in fixtures:
            if match.id in deduped:
                # A match listed in both feeds counts once; the live row wins.
                continue
            deduped[match.id] = match
            upcoming_matches += 1

        newly_seen = await self._catalog.upsert_matches(
            list(deduped.values()), observed_at=observed_at
        )
        return CatalogSyncResult(
            live_matches=live_matches,
            upcoming_matches=upcoming_matches,
            newly_seen_player_ids=tuple(sorted(newly_seen)),
            observed_at=observed_at,
        )

    async def tracking_info(self, match_id: str) -> MatchTrackingInfo | None:
        """Canonical tracking facts for one cataloged match, or None."""
        match = await self._catalog.get_match(match_id)
        if match is None:
            return None
        return MatchTrackingInfo(
            status=match.status,
            scheduled_at=match.scheduled_at,
            circuit=match.tournament.circuit,
            discipline=match.tournament.discipline,
        )
