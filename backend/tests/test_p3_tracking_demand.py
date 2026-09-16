"""Durable P3 tracking demand tests (T65).

Tracking demand comes from the pre-match coverage window, live matches and
unresolved paper positions - never from viewer leases. Challenger/ITF stay
market-only (loaded on demand by REST), and open positions keep tracking
with zero viewers.
"""

import inspect
from datetime import UTC, datetime, timedelta


from app.decision.worker import TrackingDemand, MatchTrackingInfo
from app.domain import CircuitTier, Discipline, MatchStatus

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


class FakeLinksSource:
    def __init__(self, links: dict[str, str]) -> None:
        # match_id -> market_id (active exact links)
        self.links = dict(links)

    async def active_links(self) -> dict[str, str]:
        return dict(self.links)


class FakeMatchInfo:
    def __init__(self, infos: dict[str, MatchTrackingInfo]) -> None:
        self.infos = dict(infos)

    async def __call__(self, match_id: str):
        return self.infos.get(match_id)


class FakeLedger:
    def __init__(self, position_market_ids: tuple[str, ...] = ()) -> None:
        self.position_market_ids = tuple(position_market_ids)

    async def unsettled_position_market_ids(self) -> tuple[str, ...]:
        return self.position_market_ids


def info(
    *,
    status: MatchStatus = MatchStatus.SCHEDULED,
    scheduled_at: datetime | None = NOW + timedelta(minutes=30),
    circuit: CircuitTier = CircuitTier.ATP,
    discipline: Discipline = Discipline.SINGLES,
) -> MatchTrackingInfo:
    return MatchTrackingInfo(
        status=status,
        scheduled_at=scheduled_at,
        circuit=circuit,
        discipline=discipline,
    )


def make_demand(
    links: dict[str, str],
    infos: dict[str, MatchTrackingInfo],
    positions: tuple[str, ...] = (),
    window_minutes: int = 120,
) -> TrackingDemand:
    return TrackingDemand(
        links=FakeLinksSource(links),
        match_info=FakeMatchInfo(infos),
        ledger=FakeLedger(positions),
        now=lambda: NOW,
        coverage_window=timedelta(minutes=window_minutes),
    )


async def test_live_main_tour_match_is_tracked():
    demand = make_demand(
        {"mat_1": "mkt_1"}, {"mat_1": info(status=MatchStatus.LIVE, scheduled_at=None)}
    )

    assert await demand.demanded_markets() == {"mkt_1"}


async def test_prematch_within_coverage_window_is_tracked():
    demand = make_demand(
        {"mat_1": "mkt_1"},
        {"mat_1": info(scheduled_at=NOW + timedelta(minutes=90))},
    )

    assert await demand.demanded_markets() == {"mkt_1"}


async def test_prematch_beyond_window_is_not_tracked():
    demand = make_demand(
        {"mat_1": "mkt_1"},
        {"mat_1": info(scheduled_at=NOW + timedelta(hours=6))},
    )

    assert await demand.demanded_markets() == set()


async def test_unsettled_position_is_tracked_with_zero_viewers():
    # No viewer lease store exists anywhere in this pipeline: the position
    # alone keeps the market tracked.
    demand = make_demand(
        {},
        {},
        positions=("mkt_pos",),
    )

    assert await demand.demanded_markets() == {"mkt_pos"}


async def test_challenger_and_itf_are_not_background_tracked():
    demand = make_demand(
        {"mat_c": "mkt_c", "mat_i": "mkt_i", "mat_a": "mkt_a"},
        {
            "mat_c": info(circuit=CircuitTier.CHALLENGER),
            "mat_i": info(circuit=CircuitTier.ITF),
            "mat_a": info(circuit=CircuitTier.ATP),
        },
    )

    assert await demand.demanded_markets() == {"mkt_a"}


async def test_doubles_are_not_tracked():
    demand = make_demand(
        {"mat_d": "mkt_d"}, {"mat_d": info(discipline=Discipline.DOUBLES)}
    )

    assert await demand.demanded_markets() == set()


async def test_unknown_match_info_tracks_conservatively():
    # A linked match whose info cannot load stays tracked (never silently
    # dropped) so its market keeps receiving books.
    demand = make_demand({"mat_x": "mkt_x"}, {})

    assert await demand.demanded_markets() == {"mkt_x"}


def test_demand_never_depends_on_viewer_leases():
    parameters = inspect.signature(TrackingDemand.__init__).parameters
    assert "leases" not in parameters
    assert "lease_store" not in parameters
    source = inspect.getsource(TrackingDemand)
    assert "ViewerLeaseStore" not in source
