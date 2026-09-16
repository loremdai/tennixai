"""Deterministic pre-match candidate tests (T61).

Elo updates only after a match, dynamic-rating uncertainty grows with
inactivity, HGBM features use only prior rows and a fixed seed produces
identical artifacts.
"""

from datetime import date, timedelta

import pytest

from app.prediction.data import HistoricalMatch
from app.prediction.prematch import (
    DynamicRatingCandidate,
    EloCandidate,
    HgbmCandidate,
    build_feature_matrix,
)


def make_match(
    key: str,
    day: date,
    *,
    player_a: str = "A",
    player_b: str = "B",
    winner: str = "a",
    surface: str = "hard",
    tour: str = "atp",
    fmt: str = "best_of_3",
) -> HistoricalMatch:
    return HistoricalMatch(
        match_key=key,
        date=day,
        tour=tour,
        surface=surface,
        format=fmt,
        player_a=player_a,
        player_b=player_b,
        winner=winner,
    )


def history(count: int = 40) -> tuple[HistoricalMatch, ...]:
    start = date(2024, 1, 1)
    matches = []
    for i in range(count):
        # A beats B in 70% of the synthetic history.
        winner = "a" if (i * 7) % 10 < 7 else "b"
        matches.append(
            make_match(f"m{i:03d}", start + timedelta(days=i), winner=winner)
        )
    return tuple(matches)


def test_elo_starts_neutral_and_updates_only_after_matches():
    candidate = EloCandidate()
    day = date(2025, 1, 1)
    fresh = candidate.predict_before(candidate.fit(()), make_match("q", day))
    assert fresh == pytest.approx(0.5)

    trained = candidate.fit(history())
    # A won most history; prediction for A must now favor A.
    probability = candidate.predict_before(trained, make_match("q", day))
    assert probability > 0.6


def test_elo_surface_component_uses_surface_history():
    candidate = EloCandidate()
    clay_history = tuple(
        make_match(
            f"c{i}",
            date(2024, 1, 1) + timedelta(days=i),
            surface="clay",
            winner="a" if i % 4 else "b",
        )
        for i in range(40)
    )
    grass_history = tuple(
        make_match(
            f"g{i}",
            date(2024, 1, 1) + timedelta(days=i),
            surface="grass",
            winner="b" if i % 4 else "a",
        )
        for i in range(40)
    )
    trained = candidate.fit(clay_history + grass_history)
    clay_query = make_match("q1", date(2025, 1, 1), surface="clay")
    grass_query = make_match("q2", date(2025, 1, 1), surface="grass")

    clay_probability = candidate.predict_before(trained, clay_query)
    grass_probability = candidate.predict_before(trained, grass_query)
    # A dominates on clay, B dominates on grass: surface Elo must differ.
    assert clay_probability > 0.5
    assert grass_probability < 0.5


def test_dynamic_rating_uncertainty_grows_with_inactivity():
    candidate = DynamicRatingCandidate()
    trained = candidate.fit(history())

    active_day = date(2024, 2, 15)  # right after the dense history
    idle_day = date(2025, 6, 1)  # long inactivity for both players

    active_sigma = candidate.uncertainty(trained, "A", active_day)
    idle_sigma = candidate.uncertainty(trained, "A", idle_day)
    assert idle_sigma > active_sigma

    # Prediction shrinks toward 0.5 as uncertainty grows.
    active_p = candidate.predict_before(trained, make_match("q", active_day))
    idle_p = candidate.predict_before(trained, make_match("q", idle_day))
    assert abs(idle_p - 0.5) < abs(active_p - 0.5)


def test_hgbm_features_use_only_prior_rows():
    matches = list(history(60))
    index = 30

    features_before, _ = build_feature_matrix(tuple(matches), indices=(index,))
    # Mutating future rows must not change the feature vector at `index`.
    mutated = list(matches)
    for i in range(index + 1, len(mutated)):
        mutated[i] = HistoricalMatch(
            **{
                **mutated[i].__dict__,
                "winner": "b" if mutated[i].winner == "a" else "a",
            }
        )
    features_after, _ = build_feature_matrix(tuple(mutated), indices=(index,))

    assert features_before.tolist() == features_after.tolist()

    # But changing a prior row does change the features.
    mutated_prior = list(matches)
    mutated_prior[0] = HistoricalMatch(**{**mutated_prior[0].__dict__, "winner": "b"})
    features_prior_changed, _ = build_feature_matrix(
        tuple(mutated_prior), indices=(index,)
    )
    assert features_before.tolist() != features_prior_changed.tolist()


def test_hgbm_fixed_seed_produces_identical_artifacts(tmp_path):
    matches = history(120)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = HgbmCandidate(seed=42)
    first.fit(matches)
    first.save(first_dir)

    second = HgbmCandidate(seed=42)
    second.fit(matches)
    second.save(second_dir)

    first_blob = (first_dir / "model.joblib").read_bytes()
    second_blob = (second_dir / "model.joblib").read_bytes()
    assert first_blob == second_blob

    predictions_a = first.predict(matches[-10:])
    predictions_b = second.predict(matches[-10:])
    assert predictions_a == predictions_b


def test_candidates_are_deterministic_across_runs():
    matches = history(80)
    for candidate in (EloCandidate(), DynamicRatingCandidate()):
        first = candidate.fit(matches)
        second = candidate.fit(matches)
        query = make_match("q", date(2025, 1, 1))
        assert candidate.predict_before(first, query) == pytest.approx(
            candidate.predict_before(second, query)
        )
