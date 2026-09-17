"""Composed runtime demand tests (T77).

`RuntimeDemand` unions P2 viewer-lease demand with durable P3 tracking
demand: duplicates collapse to a single active entry and P3 tracking keeps
a match alive with zero viewers. `catalog_match_info` gives `TrackingDemand`
real canonical match context (status, schedule, circuit, discipline).
"""

from datetime import UTC, datetime

from app.decision.worker import MatchTrackingInfo, TrackingDemand
from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.realtime.leases import DemandedMatch
from app.runtime.demand import RuntimeDemand, catalog_match_info

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class FakeLeases:
    def __init__(self, match_ids, *, state: str = "active") -> None:
        self.items = [
            DemandedMatch(match_id=match_id, state=state) for match_id in match_ids
        ]

    async def demanded_matches(self) -> list[DemandedMatch]:
        return list(self.items)


class FakeTracking:
    def __init__(self, market_ids) -> None:
        self.markets = set(market_ids)

    async def demanded_markets(self) -> set[str]:
        return set(self.markets)


class FakeLinks:
    def __init__(self, links: dict[str, str]) -> None:
        # match_id -> market_id (active exact links)
        self.links = dict(links)

    async def active_links(self) -> dict[str, str]:
        return dict(self.links)


class FakeLedger:
    async def unsettled_position_market_ids(self) -> tuple[str, ...]:
        return ()


def catalog_match(
    match_id: str,
    *,
    status: MatchStatus = MatchStatus.LIVE,
    scheduled_at: datetime | None = None,
    circuit: CircuitTier = CircuitTier.ATP,
    discipline: Discipline = Discipline.SINGLES,
) -> Match:
    return Match(
        id=match_id,
        status=status,
        scheduled_at=scheduled_at,
        players=(Player(id="ply_a", name="A"), Player(id="ply_b", name="B")),
        tournament=Tournament(
            id="trn_t", name="Tulln", circuit=circuit, discipline=discipline
        ),
        freshness=DataFreshness(provider="api_tennis", observed_at=NOW),
    )


class FakeCatalog:
    def __init__(self, matches) -> None:
        self.matches = {match.id: match for match in matches}

    async def get_match(self, match_id: str) -> Match | None:
        return self.matches.get(match_id)


# ---------------------------------------------------------------------------
# RuntimeDemand union semantics
# ---------------------------------------------------------------------------


async def test_runtime_demand_unions_viewer_and_paper_tracking_without_duplicates():
    demand = RuntimeDemand(
        leases=FakeLeases({"mat_view"}),
        tracking=FakeTracking({"mkt_paper"}),
        links=FakeLinks({"mat_paper": "mkt_paper"}),
    )

    assert await demand.demanded_matches() == {
        "mat_view": "active",
        "mat_paper": "active",
    }


async def test_same_match_from_both_sources_collapses_to_one_active_entry():
    demand = RuntimeDemand(
        leases=FakeLeases({"mat_1"}),
        tracking=FakeTracking({"mkt_1"}),
        links=FakeLinks({"mat_1": "mkt_1"}),
    )

    assert await demand.demanded_matches() == {"mat_1": "active"}


async def test_p3_tracking_keeps_match_alive_with_zero_viewers():
    demand = RuntimeDemand(
        leases=FakeLeases(set()),
        tracking=FakeTracking({"mkt_paper"}),
        links=FakeLinks({"mat_paper": "mkt_paper"}),
    )

    assert await demand.demanded_matches() == {"mat_paper": "active"}


async def test_empty_sources_yield_empty_demand():
    demand = RuntimeDemand(
        leases=FakeLeases(set()), tracking=FakeTracking(set()), links=FakeLinks({})
    )

    assert await demand.demanded_matches() == {}


async def test_lease_state_passes_through_when_not_tracked():
    demand = RuntimeDemand(
        leases=FakeLeases({"mat_1"}, state="grace"),
        tracking=FakeTracking(set()),
        links=FakeLinks({}),
    )

    assert await demand.demanded_matches() == {"mat_1": "grace"}


async def test_p3_tracking_promotes_grace_lease_to_active():
    demand = RuntimeDemand(
        leases=FakeLeases({"mat_1"}, state="grace"),
        tracking=FakeTracking({"mkt_1"}),
        links=FakeLinks({"mat_1": "mkt_1"}),
    )

    assert await demand.demanded_matches() == {"mat_1": "active"}


async def test_tracked_market_without_active_link_creates_no_match_demand():
    # Unsettled-position markets without a link row cannot be mapped to a
    # match; they keep the market worker alive but never open a sports feed.
    demand = RuntimeDemand(
        leases=FakeLeases(set()),
        tracking=FakeTracking({"mkt_orphan"}),
        links=FakeLinks({}),
    )

    assert await demand.demanded_matches() == {}


# ---------------------------------------------------------------------------
# catalog_match_info factory
# ---------------------------------------------------------------------------


async def test_catalog_match_info_maps_canonical_match():
    scheduled = NOW.replace(hour=15)
    catalog = FakeCatalog(
        [
            catalog_match(
                "mat_1",
                status=MatchStatus.SCHEDULED,
                scheduled_at=scheduled,
                circuit=CircuitTier.WTA,
                discipline=Discipline.SINGLES,
            )
        ]
    )

    info = await catalog_match_info(catalog)("mat_1")

    assert info == MatchTrackingInfo(
        status=MatchStatus.SCHEDULED,
        scheduled_at=scheduled,
        circuit=CircuitTier.WTA,
        discipline=Discipline.SINGLES,
    )


async def test_catalog_match_info_returns_none_for_unknown_match():
    catalog = FakeCatalog([])

    assert await catalog_match_info(catalog)("mat_missing") is None


async def test_tracking_demand_consumes_catalog_match_info_factory():
    catalog = FakeCatalog([catalog_match("mat_1", status=MatchStatus.LIVE)])
    tracking = TrackingDemand(
        links=FakeLinks({"mat_1": "mkt_1"}),
        match_info=catalog_match_info(catalog),
        ledger=FakeLedger(),
        now=lambda: NOW,
    )

    assert await tracking.demanded_markets() == {"mkt_1"}
