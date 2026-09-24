from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.identity import MemoryIdentityRepository
from app.providers.api_tennis import STAT_NAME_MAP
from app.providers.replay import ReplayTennisProvider


FIXTURE = Path(__file__).parent / "fixtures" / "replay" / "live_match.jsonl"


class ReplayClock:
    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self._now = 0.0

    def now(self) -> float:
        return self._now

    def utcnow(self) -> datetime:
        return datetime.fromtimestamp(self._now, tz=timezone.utc)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


@pytest.mark.asyncio
async def test_replay_emits_scripted_events_in_order_and_scales_time() -> None:
    clock = ReplayClock()
    provider = ReplayTennisProvider.from_file(
        FIXTURE,
        identities=MemoryIdentityRepository(),
        clock=clock,
        speed=20.0,
    )

    events = [event async for event in provider.stream_match("replay-live")]

    assert [event.kind for event in events] == [
        "snapshot",
        "point",
        "duplicate",
        "statistics",
        "correction",
        "disconnect",
        "reconcile",
        "finished",
    ]
    assert clock.sleeps == [0.05, 0.025, 0.025, 0.025, 0.025, 0.15, 0.05]


@pytest.mark.asyncio
async def test_replay_materializes_canonical_identity_and_full_statistics() -> None:
    provider = ReplayTennisProvider.from_file(
        FIXTURE,
        identities=MemoryIdentityRepository(),
        speed=100.0,
    )

    matches = await provider.get_live_matches()
    assert len(matches) == 1
    match = matches[0]
    assert match.id.startswith("mat_")
    assert all(player.id.startswith("ply_") for player in match.players)
    assert match.tournament.id.startswith("trn_")
    assert "replay-live" not in match.id

    initial = await provider.get_match_snapshot(match.id)
    assert initial.state_version == 0
    assert initial.statistics == ()

    events = [event async for event in provider.stream_match("replay-live")]
    statistics_event = next(event for event in events if event.kind == "statistics")
    candidate = await provider.to_candidate(statistics_event)

    assert candidate is not None
    assert candidate.match.id == match.id
    assert len(candidate.statistics) == 22
    assert all(stat.match_id == match.id for stat in candidate.statistics)
    expected_units = {name: unit for name, unit in STAT_NAME_MAP.values()}
    assert {stat.name for stat in candidate.statistics} == set(expected_units)
    assert {stat.name: stat.unit for stat in candidate.statistics} == expected_units
    expected_percentages = {
        "service_games_won": (85.7, 80.0),
        "break_points_saved": (66.7, 50.0),
        "break_points_converted": (25.0, 40.0),
        "return_games_won": (20.0, 25.0),
        "net_points_won": (63.6, 57.1),
        "total_points_won": (56.4, 43.6),
        "total_games_won": (53.6, 46.4),
    }
    assert {
        stat.name.value: (stat.player1_value, stat.player2_value)
        for stat in candidate.statistics
        if stat.name.value in expected_percentages
    } == expected_percentages
    assert all(point.match_id == match.id for point in candidate.points)
    assert all("replay-live" not in player.id for player in candidate.match.players)
