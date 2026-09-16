"""Empirical-Bayes serve shrinkage and PBP-derived evidence tests (T62)."""

from datetime import UTC, datetime

import pytest

from app.domain import MatchScore, PointEvent
from app.prediction.live import (
    LiveServeEstimator,
    ServeEvidence,
    count_service_points,
    shrink_serve_prior,
)
from app.prediction.scoring import ServePointPrior

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def point(
    sequence: int,
    *,
    server: str | None = "ply_a",
    winner: str | None = "ply_a",
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
        observed_at=NOW,
        provider="test",
        source_fingerprint=f"fp_{sequence}",
    )


def test_small_live_sample_stays_near_prior():
    posterior = shrink_serve_prior(0.6, served=2, won=2, prior_strength=25.0)
    assert posterior == pytest.approx((2 + 25 * 0.6) / 27)
    assert abs(posterior - 0.6) < 0.05


def test_larger_samples_move_monotonically_toward_observation():
    observation = 0.75
    posteriors = [
        shrink_serve_prior(0.6, served=n, won=int(n * observation), prior_strength=25.0)
        for n in (10, 40, 100, 400)
    ]
    assert all(0.6 <= value <= observation for value in posteriors)
    assert posteriors == sorted(posteriors)
    assert posteriors[-1] == pytest.approx(0.75, abs=0.02)


def test_zero_sample_returns_prior_unchanged():
    assert shrink_serve_prior(0.63, served=0, won=0) == pytest.approx(0.63)


def test_count_service_points_only_uses_points_before_prediction_state():
    points = (
        point(1, server="ply_a", winner="ply_a"),
        point(2, server="ply_a", winner="ply_b"),
        point(3, server="ply_b", winner="ply_b"),
        point(4, server="ply_b", winner="ply_a"),
        point(5, server="ply_a", winner="ply_a"),
    )

    evidence = count_service_points(
        points, up_to_sequence=5, p1_id="ply_a", p2_id="ply_b"
    )

    assert evidence == ServeEvidence(
        p1_points_served=2, p1_points_won=1, p2_points_served=2, p2_points_won=1
    )


def test_count_skips_indeterminate_and_foreign_points():
    points = (
        point(1, server="ply_a", winner=None),  # indeterminate
        point(2, server=None, winner="ply_a"),  # server unknown
        point(3, server="ply_c", winner="ply_c"),  # not one of the two players
        point(4, server="ply_a", winner="ply_a"),
    )

    evidence = count_service_points(
        points, up_to_sequence=99, p1_id="ply_a", p2_id="ply_b"
    )

    assert evidence.p1_points_served == 1
    assert evidence.p1_points_won == 1
    assert evidence.p2_points_served == 0


def test_correction_recomputes_deterministically_from_affected_sequence():
    original = tuple(
        point(index, server="ply_a", winner="ply_a" if index % 2 else "ply_b")
        for index in range(1, 11)
    )
    corrected_list = list(original)
    corrected_list[4] = point(
        5, server="ply_a", winner="ply_b"
    )  # flip the winner at sequence 5
    corrected = tuple(corrected_list)

    before = count_service_points(
        original, up_to_sequence=99, p1_id="ply_a", p2_id="ply_b"
    )
    after_first = count_service_points(
        corrected, up_to_sequence=99, p1_id="ply_a", p2_id="ply_b"
    )
    after_second = count_service_points(
        corrected, up_to_sequence=99, p1_id="ply_a", p2_id="ply_b"
    )

    assert after_first == after_second  # deterministic
    assert after_first.p1_points_won == before.p1_points_won - 1
    assert after_first.p1_points_served == before.p1_points_served


def test_estimator_combines_both_sides_independently():
    estimator = LiveServeEstimator(prior_strength=20.0)
    prior = ServePointPrior(p1_serve_win=0.64, p2_serve_win=0.62)
    evidence = ServeEvidence(
        p1_points_served=60, p1_points_won=45, p2_points_served=3, p2_points_won=2
    )

    posterior = estimator.estimate(prior, evidence)

    # p1: 75% observed over 60 points moves the prior up.
    assert posterior.p1_serve_win > 0.64
    # p2: three points keep the posterior near the prior.
    assert posterior.p2_serve_win == pytest.approx(0.62, abs=0.03)
