"""Formula and invariance gates for the Recent Control Index v1 engine.

The index is descriptive, not predictive: serve-corrected residuals smoothed
by an EWMA, with key-point flags kept as annotations only.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain import MatchScore, PointEvent
from app.momentum import ALGORITHM_VERSION
from app.momentum.calibration import Calibration, CohortPrior
from app.momentum.engine import RecentControlEngine

FOCAL = "ply_a"
OTHER = "ply_b"


def calibration(alpha: float = 0.5, scale: float = 1.0) -> Calibration:
    return Calibration(
        schema_version=1,
        algorithm_version=ALGORITHM_VERSION,
        generated_at="2026-09-09T00:00:00Z",
        alpha=alpha,
        scale=scale,
        global_prior=CohortPrior(serve_win_prior=0.6, prior_strength=4.0, sample_points=10_000),
        cohorts={},
    )


@pytest.fixture()
def engine() -> RecentControlEngine:
    return RecentControlEngine(calibration())


def point(
    sequence: int,
    server: str | None = FOCAL,
    winner: str | None = FOCAL,
    *,
    break_point: bool = False,
    set_point: bool = False,
    match_point: bool = False,
) -> PointEvent:
    return PointEvent(
        id=f"pe_{sequence}",
        match_id="mat_1",
        sequence=sequence,
        set_number=1,
        game_number=1,
        point_number=sequence,
        server_player_id=server,
        winner_player_id=winner,
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=("0", "0")),
        is_break_point=break_point,
        is_set_point=set_point,
        is_match_point=match_point,
        observed_at=datetime(2026, 9, 9, 12, 0, tzinfo=UTC) + timedelta(seconds=sequence),
        provider="fake",
        source_fingerprint=f"fp-{sequence}",
    )


def swap_players(points: list[PointEvent]) -> list[PointEvent]:
    def swap(player_id: str | None) -> str | None:
        if player_id == FOCAL:
            return OTHER
        if player_id == OTHER:
            return FOCAL
        return player_id

    return [
            p.model_copy(
            update={
                "server_player_id": swap(p.server_player_id),
                "winner_player_id": swap(p.winner_player_id),
            }
        )
        for p in points
    ]


def history() -> list[PointEvent]:
    return [
        point(1, FOCAL, FOCAL),
        point(2, OTHER, OTHER),
        point(3, FOCAL, FOCAL),
        point(4, OTHER, FOCAL),
        point(5, FOCAL, OTHER),
        point(6, OTHER, OTHER),
        point(7, FOCAL, FOCAL),
    ]


def test_player_swap_negates_recent_control(engine):
    points = history()
    original = engine.compute(points, focal_player_id=FOCAL)
    swapped = engine.compute(swap_players(points), focal_player_id=FOCAL)
    assert swapped[-1].value == pytest.approx(-original[-1].value)
    assert [o.value for o in swapped] == pytest.approx([-o.value for o in original])


def test_return_point_surprise_exceeds_routine_hold(engine):
    hold = engine.update([], point(1, FOCAL, FOCAL), focal_player_id=FOCAL)
    return_win = engine.update([], point(1, OTHER, FOCAL), focal_player_id=FOCAL)
    assert return_win.value > hold.value > 0


def test_key_point_flag_has_no_fixed_numeric_multiplier(engine):
    ordinary = engine.update(history(), point(8, FOCAL, FOCAL, break_point=False))
    flagged = engine.update(history(), point(8, FOCAL, FOCAL, break_point=True))
    assert flagged.value == ordinary.value
    set_flagged = engine.update(
        history(), point(8, FOCAL, FOCAL, set_point=True, match_point=True)
    )
    assert set_flagged.value == ordinary.value


def test_no_future_leakage(engine):
    points = history()
    full = engine.compute(points, focal_player_id=FOCAL)
    for length in range(1, len(points) + 1):
        prefix = engine.compute(points[:length], focal_player_id=FOCAL)
        assert [o.value for o in prefix] == pytest.approx([o.value for o in full[:length]])


def test_indeterminate_winner_does_not_update(engine):
    base = engine.compute(history(), focal_player_id=FOCAL)
    with_pending = engine.compute(
        [*history(), point(8, FOCAL, None)], focal_player_id=FOCAL
    )
    assert [o.value for o in with_pending] == pytest.approx([o.value for o in base])
    assert len(with_pending) == len(base)


def test_fewer_than_six_determinate_points_is_provisional(engine):
    observations = engine.compute(history()[:5], focal_player_id=FOCAL)
    assert len(observations) == 5
    assert all(o.is_provisional for o in observations)
    grown = engine.compute(history()[:6], focal_player_id=FOCAL)
    assert all(o.is_provisional for o in grown[:5])
    assert grown[5].is_provisional is False


def test_output_is_bounded(engine):
    points = [point(i, None, FOCAL) for i in range(1, 201)]
    observations = engine.compute(points, focal_player_id=FOCAL)
    assert all(-100.0 <= o.value <= 100.0 for o in observations)
    assert observations[-1].value == pytest.approx(100.0)


def test_deterministic_replay_and_correction_recompute(engine):
    wrong = [*history()[:3], point(4, OTHER, OTHER), *history()[4:]]
    corrected = [*history()[:3], point(4, OTHER, FOCAL), *history()[4:]]

    first = engine.compute(wrong, focal_player_id=FOCAL)
    second = engine.compute(wrong, focal_player_id=FOCAL)
    assert [o.value for o in first] == pytest.approx([o.value for o in second])

    recomputed = engine.compute(corrected, focal_player_id=FOCAL)
    assert [o.value for o in recomputed[:3]] == pytest.approx([o.value for o in first[:3]])
    assert recomputed[3].value != pytest.approx(first[3].value)
    assert recomputed[-1].value != pytest.approx(first[-1].value)


def test_serve_shrinkage_dampens_repeated_holds(engine):
    holds = [point(i, FOCAL, FOCAL) for i in range(1, 13)]
    observations = engine.compute(holds, focal_player_id=FOCAL)
    first_gain = observations[0].value
    last_gain = observations[-1].value - observations[-2].value
    assert first_gain > 0
    assert last_gain < first_gain


def test_input_summary_uses_pre_point_serve_history(engine):
    observations = engine.compute(
        [point(1, FOCAL, FOCAL), point(2, FOCAL, OTHER)],
        focal_player_id=FOCAL,
    )

    assert "serve=0/0" in observations[0].input_summary
    assert "serve=1/1" in observations[1].input_summary


def test_observations_carry_algorithm_version_and_leader(engine):
    observations = engine.compute(history(), focal_player_id=FOCAL)
    assert all(o.algorithm_version == ALGORITHM_VERSION for o in observations)
    assert observations[-1].leader_player_id in {FOCAL, OTHER, None}
    positive = engine.compute([point(1, OTHER, FOCAL)], focal_player_id=FOCAL)
    assert positive[-1].leader_player_id == FOCAL
    negative = engine.compute([point(1, FOCAL, OTHER)], focal_player_id=FOCAL)
    assert negative[-1].leader_player_id == OTHER


def test_missing_server_falls_back_to_coin_flip_prior(engine):
    no_server = engine.compute([point(1, None, FOCAL)], focal_player_id=FOCAL)
    assert no_server[-1].value > 0
