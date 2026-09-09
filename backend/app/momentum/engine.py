"""Recent Control Index v1 runtime formula.

For focal player A and determinate point i:

    yᵢ = 1 if A wins the point else 0
    pᵢ = pre-point probability that A wins, from the cohort serve prior
         shrunk by this match's completed service points (strictly pre-point)
    rᵢ = 2 × (yᵢ - p)
    M = (1 - α) × Mᵢ₋₁ + α × rᵢ
    indexᵢ = clip(100 × Mᵢ / scale, -100, 100)

Key-point flags never enter the formula; they stay PBP annotations. Points
without a determinate winner never update the series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.domain import (
    CircuitTier,
    Discipline,
    Gender,
    MomentumObservation,
    PointEvent,
)

ALGORITHM_VERSION = "recent-control-v1"
PROVISIONAL_THRESHOLD = 6


@dataclass(frozen=True)
class CohortPrior:
    serve_win_prior: float
    prior_strength: float
    sample_points: int


@dataclass(frozen=True)
class Calibration:
    schema_version: int
    algorithm_version: str
    generated_at: str
    alpha: float
    scale: float
    global_prior: CohortPrior
    cohorts: Mapping[str, CohortPrior]

    def prior_for(
        self, circuit: CircuitTier, gender: Gender, discipline: Discipline
    ) -> CohortPrior:
        return self.cohorts.get(
            f"{circuit.value}|{gender.value}|{discipline.value}", self.global_prior
        )


def _default_calibration() -> Calibration:
    from app.momentum.calibration import load_calibration

    return load_calibration()


class RecentControlEngine:
    """Deterministic EWMA over serve-corrected point residuals."""

    def __init__(self, calibration: Calibration | None = None) -> None:
        self.calibration = calibration if calibration is not None else _default_calibration()

    def compute(
        self,
        points: Sequence[PointEvent],
        *,
        focal_player_id: str,
        cohort: tuple[CircuitTier, Gender, Discipline] | None = None,
        match_id: str | None = None,
        state_version: int = 0,
    ) -> list[MomentumObservation]:
        prior = (
            self.calibration.prior_for(*cohort)
            if cohort is not None
            else self.calibration.global_prior
        )
        alpha = self.calibration.alpha
        scale = self.calibration.scale

        smoothed = 0.0
        counted = 0
        serve_points: dict[str, int] = {}
        serve_won: dict[str, int] = {}
        observations: list[MomentumObservation] = []
        for point in sorted(points, key=lambda item: item.sequence):
            if point.winner_player_id is None:
                continue
            server = point.server_player_id
            server_points_before = serve_points.get(server, 0) if server else 0
            server_won_before = serve_won.get(server, 0) if server else 0
            if server is None:
                probability = 0.5
            else:
                strength = prior.prior_strength
                server_prior = (
                    strength * prior.serve_win_prior + server_won_before
                ) / (
                    strength + server_points_before
                )
                probability = server_prior if server == focal_player_id else 1.0 - server_prior
            outcome = 1.0 if point.winner_player_id == focal_player_id else 0.0
            residual = 2.0 * (outcome - probability)
            smoothed = (1.0 - alpha) * smoothed + alpha * residual
            counted += 1
            if server is not None:
                serve_points[server] = serve_points.get(server, 0) + 1
                if point.winner_player_id == server:
                    serve_won[server] = serve_won.get(server, 0) + 1
            value = max(-100.0, min(100.0, 100.0 * smoothed / scale))
            observations.append(
                MomentumObservation(
                    match_id=match_id if match_id is not None else point.match_id,
                    point_sequence=point.sequence,
                    state_version=state_version,
                    algorithm_version=ALGORITHM_VERSION,
                    value=value,
                    leader_player_id=_leader(point, focal_player_id, value),
                    is_provisional=counted < PROVISIONAL_THRESHOLD,
                    as_of=point.observed_at,
                    input_summary=(
                        f"n={counted};alpha={alpha};scale={scale};"
                        f"prior={probability:.3f};"
                        f"serve={server_points_before}/{server_won_before}"
                    ),
                )
            )
        return observations

    def update(
        self,
        history: Sequence[PointEvent],
        point: PointEvent,
        focal_player_id: str | None = None,
        *,
        cohort: tuple[CircuitTier, Gender, Discipline] | None = None,
        state_version: int = 0,
    ) -> MomentumObservation:
        focal = focal_player_id or _default_focal(history, point)
        observations = self.compute(
            [*history, point],
            focal_player_id=focal,
            cohort=cohort,
            state_version=state_version,
        )
        return observations[-1]


def _default_focal(history: Sequence[PointEvent], point: PointEvent) -> str:
    for candidate in (*history, point):
        if candidate.server_player_id is not None:
            return candidate.server_player_id
    raise ValueError("cannot infer a focal player without any server")


def _leader(point: PointEvent, focal_player_id: str, value: float) -> str | None:
    if value == 0:
        return None
    if value > 0:
        return focal_player_id
    others = {
        player_id
        for player_id in (point.server_player_id, point.winner_player_id)
        if player_id is not None and player_id != focal_player_id
    }
    return others.pop() if len(others) == 1 else None


def recompute_observations(
    points: Sequence[PointEvent],
    *,
    focal_player_id: str,
    match_id: str,
    state_version: int,
    cohort: tuple[CircuitTier, Gender, Discipline] | None = None,
    calibration: Calibration | None = None,
) -> tuple[MomentumObservation, ...]:
    engine = RecentControlEngine(calibration)
    return tuple(
        engine.compute(
            points,
            focal_player_id=focal_player_id,
            cohort=cohort,
            match_id=match_id,
            state_version=state_version,
        )
    )
