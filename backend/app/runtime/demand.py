"""Composed live demand for the local runtime role (T77).

`RuntimeDemand` unifies the P2 viewer-lease demand and the durable P3
tracking demand into one match-level index for the runtime-owned
`RealtimeWorker`: one upstream subscription per demanded match regardless
of how many sources want it, and P3 paper tracking keeps a match alive
with zero viewers. `catalog_match_info` builds the real `match_info`
callable for `TrackingDemand` from the canonical match catalog — status,
schedule, circuit and discipline only; provider payloads and external
identifiers never pass through this module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.decision.worker import MatchTrackingInfo
from app.runtime.catalog import MatchCatalogStore

ACTIVE = "active"


class RuntimeDemand:
    """Union of viewer-lease and durable P3 tracking demand, by match ID.

    - `leases` is the P2 `ViewerLeaseStore`; its demand states ("active" /
      "grace") pass through unchanged.
    - `tracking` is the P3 `TrackingDemand`; its demanded market IDs are
      mapped back to match IDs through `links` (`active_links()` returns
      match_id -> market_id).
    - A match demanded by both sources collapses to a single "active"
      entry; durable tracking never downgrades and always keeps the match
      alive with zero viewers.
    """

    def __init__(self, *, leases, tracking, links) -> None:
        self._leases = leases
        self._tracking = tracking
        self._links = links

    async def demanded_matches(self) -> dict[str, str]:
        demanded: dict[str, str] = {
            item.match_id: item.state for item in await self._leases.demanded_matches()
        }
        tracked_markets = await self._tracking.demanded_markets()
        if not tracked_markets:
            return demanded
        for match_id, market_id in (await self._links.active_links()).items():
            if market_id in tracked_markets:
                demanded[match_id] = ACTIVE
        return demanded


def catalog_match_info(
    catalog: MatchCatalogStore,
) -> Callable[[str], Awaitable[MatchTrackingInfo | None]]:
    """Build the `TrackingDemand` `match_info` callable on the canonical catalog."""

    async def match_info(match_id: str) -> MatchTrackingInfo | None:
        match = await catalog.get_match(match_id)
        if match is None:
            return None
        return MatchTrackingInfo(
            status=match.status,
            scheduled_at=match.scheduled_at,
            circuit=match.tournament.circuit,
            discipline=match.tournament.discipline,
        )

    return match_info
