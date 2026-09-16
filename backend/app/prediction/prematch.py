"""Deterministic pre-match probability candidates (T61).

Three benchmark candidates per spec §6.1: overall+surface Elo, a dynamic
rating with inactivity-driven uncertainty, and an HGBM challenger. Features
are built strictly from rows before the prediction point; nothing here ever
reads market data.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import joblib
import numpy as np

from app.prediction.data import HistoricalMatch

FEATURE_SCHEMA_VERSION = "prematch-features-v1"

FEATURE_NAMES = (
    "win_rate_a",
    "win_rate_b",
    "surface_win_rate_a",
    "surface_win_rate_b",
    "log_matches_a",
    "log_matches_b",
    "days_since_last_a",
    "days_since_last_b",
    "rank_diff",
)


@dataclass(frozen=True)
class PlayerTally:
    played: int
    won: int
    surface_played: dict[str, int]
    surface_won: dict[str, int]
    last_seen: date | None


@dataclass(frozen=True)
class EloState:
    overall: dict[str, float] = field(default_factory=dict)
    surface: dict[str, dict[str, float]] = field(default_factory=dict)
    as_of: date | None = None


@dataclass(frozen=True)
class DynamicState:
    rating: dict[str, float] = field(default_factory=dict)
    sigma: dict[str, float] = field(default_factory=dict)
    last_seen: dict[str, date] = field(default_factory=dict)
    as_of: date | None = None


def _win(player_side: str, match: HistoricalMatch) -> bool:
    return match.winner == player_side


class EloCandidate:
    """Overall + surface Elo. Ratings update only after a completed match."""

    name = "surface_elo"
    version = "elo-v1"
    complexity_rank = 1
    k_factor = 24.0
    surface_k = 16.0
    surface_weight = 0.6

    def fit(self, matches: Sequence[HistoricalMatch]) -> EloState:
        self._fitted = None
        overall: dict[str, float] = {}
        surface: dict[str, dict[str, float]] = {}
        last_date: date | None = None
        for match in sorted(matches, key=lambda item: (item.date, item.match_key)):
            last_date = match.date
            rating_a = overall.get(match.player_a, 1500.0)
            rating_b = overall.get(match.player_b, 1500.0)
            surface_a = surface.setdefault(match.surface, {})
            delta_a = surface_a.get(match.player_a, 0.0)
            delta_b = surface_a.get(match.player_b, 0.0)
            strength_a = rating_a + self.surface_weight * delta_a
            strength_b = rating_b + self.surface_weight * delta_b
            expected_a = 1.0 / (1.0 + 10 ** ((strength_b - strength_a) / 400.0))
            score_a = 1.0 if match.winner == "a" else 0.0
            overall[match.player_a] = rating_a + self.k_factor * (score_a - expected_a)
            overall[match.player_b] = rating_b + self.k_factor * (
                (1.0 - score_a) - (1.0 - expected_a)
            )
            surface_a[match.player_a] = delta_a + self.surface_k * (
                score_a - expected_a
            )
            surface_a[match.player_b] = delta_b + self.surface_k * (
                (1.0 - score_a) - (1.0 - expected_a)
            )
        state = EloState(overall=overall, surface=surface, as_of=last_date)
        self._fitted = state
        return state

    def predict_before(self, state: EloState, match: HistoricalMatch) -> float:
        rating_a = state.overall.get(match.player_a, 1500.0)
        rating_b = state.overall.get(match.player_b, 1500.0)
        surface_map = state.surface.get(match.surface, {})
        delta_a = surface_map.get(match.player_a, 0.0)
        delta_b = surface_map.get(match.player_b, 0.0)
        strength_a = rating_a + self.surface_weight * delta_a
        strength_b = rating_b + self.surface_weight * delta_b
        return 1.0 / (1.0 + 10 ** ((strength_b - strength_a) / 400.0))

    def predict_sequence(
        self,
        state: EloState,
        matches: Sequence[HistoricalMatch],
        indices: Sequence[int],
    ) -> list[float]:
        return [self.predict_before(state, matches[index]) for index in indices]

    def save(self, directory: Path, state: EloState | None = None) -> None:
        state = state if state is not None else self._fitted
        if state is None:
            raise RuntimeError("candidate not fitted")
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "kind": self.name,
                "version": self.version,
                "overall": dict(sorted(state.overall.items())),
                "surface": {
                    surface: dict(sorted(values.items()))
                    for surface, values in sorted(state.surface.items())
                },
            },
            directory / "model.joblib",
        )


class DynamicRatingCandidate:
    """Dynamic Bradley–Terry style rating whose uncertainty grows while a
    player is inactive; predictions shrink toward 0.5 with sigma."""

    name = "dynamic_rating"
    version = "dynamic-v1"
    complexity_rank = 2
    k_factor = 24.0
    base_sigma = 60.0
    drift_per_day = 0.35

    def fit(self, matches: Sequence[HistoricalMatch]) -> DynamicState:
        self._fitted = None
        rating: dict[str, float] = {}
        sigma: dict[str, float] = {}
        last_seen: dict[str, date] = {}
        last_date: date | None = None
        for match in sorted(matches, key=lambda item: (item.date, item.match_key)):
            last_date = match.date
            for player in (match.player_a, match.player_b):
                if player in last_seen:
                    idle = (match.date - last_seen[player]).days
                    sigma[player] = math.sqrt(
                        sigma.get(player, self.base_sigma) ** 2
                        + max(idle, 0) * self.drift_per_day**2 * 30.0
                    )
                else:
                    sigma.setdefault(player, self.base_sigma * 2)
                last_seen[player] = match.date
            rating_a = rating.get(match.player_a, 1500.0)
            rating_b = rating.get(match.player_b, 1500.0)
            scale = math.sqrt(
                self.base_sigma**2
                + sigma.get(match.player_a, 0) ** 2
                + sigma.get(match.player_b, 0) ** 2
            )
            expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / scale * 4.0))
            score_a = 1.0 if match.winner == "a" else 0.0
            rating[match.player_a] = rating_a + self.k_factor * (score_a - expected_a)
            rating[match.player_b] = rating_b + self.k_factor * (
                (1.0 - score_a) - (1.0 - expected_a)
            )
            # A result shrinks uncertainty toward the base level.
            for player in (match.player_a, match.player_b):
                sigma[player] = math.sqrt(
                    0.85 * sigma.get(player, self.base_sigma) ** 2
                    + 0.15 * self.base_sigma**2
                )
        state = DynamicState(
            rating=rating, sigma=sigma, last_seen=last_seen, as_of=last_date
        )
        self._fitted = state
        return state

    def uncertainty(self, state: DynamicState, player: str, day: date) -> float:
        sigma = state.sigma.get(player, self.base_sigma * 2)
        last = state.last_seen.get(player)
        if last is not None:
            idle = max((day - last).days, 0)
            sigma = math.sqrt(sigma**2 + idle * self.drift_per_day**2 * 30.0)
        return sigma

    def predict_before(self, state: DynamicState, match: HistoricalMatch) -> float:
        rating_a = state.rating.get(match.player_a, 1500.0)
        rating_b = state.rating.get(match.player_b, 1500.0)
        sigma_a = self.uncertainty(state, match.player_a, match.date)
        sigma_b = self.uncertainty(state, match.player_b, match.date)
        scale = math.sqrt(self.base_sigma**2 + sigma_a**2 + sigma_b**2)
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / scale * 4.0))

    def predict_sequence(
        self,
        state: DynamicState,
        matches: Sequence[HistoricalMatch],
        indices: Sequence[int],
    ) -> list[float]:
        return [self.predict_before(state, matches[index]) for index in indices]

    def save(self, directory: Path, state: DynamicState | None = None) -> None:
        state = state if state is not None else self._fitted
        if state is None:
            raise RuntimeError("candidate not fitted")
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "kind": self.name,
                "version": self.version,
                "rating": dict(sorted(state.rating.items())),
                "sigma": dict(sorted(state.sigma.items())),
            },
            directory / "model.joblib",
        )


def _tallies(matches: Sequence[HistoricalMatch]) -> dict[str, PlayerTally]:
    tallies: dict[str, PlayerTally] = {}

    def bump(player: str, side: str, match: HistoricalMatch) -> None:
        current = tallies.get(player)
        played = 0 if current is None else current.played
        won = 0 if current is None else current.won
        surface_played = {} if current is None else dict(current.surface_played)
        surface_won = {} if current is None else dict(current.surface_won)
        played += 1
        won += 1 if _win(side, match) else 0
        surface_played[match.surface] = surface_played.get(match.surface, 0) + 1
        if _win(side, match):
            surface_won[match.surface] = surface_won.get(match.surface, 0) + 1
        tallies[player] = PlayerTally(
            played=played,
            won=won,
            surface_played=surface_played,
            surface_won=surface_won,
            last_seen=match.date,
        )

    for match in sorted(matches, key=lambda item: (item.date, item.match_key)):
        bump(match.player_a, "a", match)
        bump(match.player_b, "b", match)
    return tallies


def _feature_row(
    tallies: dict[str, PlayerTally], match: HistoricalMatch
) -> list[float]:
    tally_a = tallies.get(match.player_a)
    tally_b = tallies.get(match.player_b)

    def rates(tally: PlayerTally | None) -> tuple[float, float, float, float]:
        if tally is None or tally.played == 0:
            return (0.5, 0.5, 0.0, 0.0)
        overall = tally.won / tally.played
        played = tally.surface_played.get(match.surface, 0)
        surface = tally.surface_won.get(match.surface, 0) / played if played else 0.5
        return (overall, surface, math.log1p(tally.played), float(played))

    rate_a, surface_a, log_a, _ = rates(tally_a)
    rate_b, surface_b, log_b, _ = rates(tally_b)
    idle_a = (match.date - tally_a.last_seen).days / 30.0 if tally_a else 12.0
    idle_b = (match.date - tally_b.last_seen).days / 30.0 if tally_b else 12.0
    # A missing rank is neutral (0), never NaN: an all-NaN column is not
    # learnable signal and must not depend on vendor completeness.
    rank_diff = 0.0
    if match.rank_a is not None and match.rank_b is not None:
        rank_diff = float(match.rank_a - match.rank_b)
    return [
        rate_a,
        rate_b,
        surface_a,
        surface_b,
        log_a,
        log_b,
        idle_a,
        idle_b,
        rank_diff,
    ]


def build_feature_matrix(
    matches: Sequence[HistoricalMatch], indices: Sequence[int] | None = None
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Feature vectors built strictly from rows before each index."""
    if indices is None:
        indices = range(len(matches))
    ordered = sorted(matches, key=lambda item: (item.date, item.match_key))
    position = {id(match): rank for rank, match in enumerate(ordered)}
    rows: list[list[float]] = []
    for index in indices:
        target = matches[index]
        rank = position.get(id(target))
        if rank is None:  # target itself is part of the sequence
            rank = index
        prior = ordered[:rank]
        tallies = _tallies(prior)
        rows.append(_feature_row(tallies, target))
    return np.asarray(rows, dtype=float), FEATURE_NAMES


class HgbmCandidate:
    """HistGradientBoosting challenger. Never relearns scoring rules; it can
    only exploit features derived from prior structured rows."""

    name = "hgbm"
    version = "hgbm-v1"
    complexity_rank = 3

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._model = None

    def fit(self, matches: Sequence[HistoricalMatch]):
        from sklearn.ensemble import HistGradientBoostingClassifier

        ordered = sorted(matches, key=lambda item: (item.date, item.match_key))
        features, _ = build_feature_matrix(
            ordered, indices=[i for i in range(1, len(ordered))]
        )
        labels = np.asarray(
            [1 if match.winner == "a" else 0 for match in ordered[1:]], dtype=int
        )
        model = HistGradientBoostingClassifier(
            random_state=self.seed,
            max_depth=3,
            max_iter=80,
            learning_rate=0.08,
            min_samples_leaf=8,
        )
        model.fit(features, labels)
        self._model = model
        self._fitted = model
        return model

    def predict_before(self, model, match: HistoricalMatch) -> float:
        raise NotImplementedError(
            "HGBM predictions require sequence context; use predict_sequence"
        )

    def predict_sequence(
        self,
        model,
        matches: Sequence[HistoricalMatch],
        indices: Sequence[int],
    ) -> list[float]:
        features, _ = build_feature_matrix(matches, indices=indices)
        probabilities = model.predict_proba(features)[:, 1]
        return [float(value) for value in probabilities]

    def predict(self, matches: Sequence[HistoricalMatch]) -> list[float]:
        """Walk-forward predictions for the tail of a sequence."""
        if self._model is None:
            raise RuntimeError("candidate not fitted")
        start = max(len(matches) - 10, 1)
        indices = list(range(start, len(matches)))
        return self.predict_sequence(self._model, matches, indices)

    def save(self, directory: Path, model=None) -> None:
        model = model if model is not None else self._model
        if model is None:
            raise RuntimeError("candidate not fitted")
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "kind": self.name,
                "version": self.version,
                "seed": self.seed,
                "model": model,
            },
            directory / "model.joblib",
        )


PREMATCH_CANDIDATES = (EloCandidate, DynamicRatingCandidate, HgbmCandidate)
