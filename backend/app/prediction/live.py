"""Live serve-point evidence and empirical-Bayes shrinkage (T62).

Service-point ability starts from the pre-match prior and absorbs in-match
evidence through beta-binomial (empirical-Bayes) shrinkage. Only points
strictly before the prediction state are counted; indeterminate winners and
unknown servers are skipped, never guessed. A PBP correction simply changes
the counted set, so recomputation from the affected sequence is
deterministic.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain import PointEvent
from app.prediction.scoring import ServePointPrior

DEFAULT_PRIOR_STRENGTH = 25.0


@dataclass(frozen=True)
class ServeEvidence:
    p1_points_served: int = 0
    p1_points_won: int = 0
    p2_points_served: int = 0
    p2_points_won: int = 0


def count_service_points(
    points: Sequence[PointEvent],
    *,
    up_to_sequence: int,
    p1_id: str,
    p2_id: str,
) -> ServeEvidence:
    """Count determined service points strictly before `up_to_sequence`."""
    p1_served = p1_won = p2_served = p2_won = 0
    for event in points:
        if event.sequence >= up_to_sequence:
            continue
        server = event.server_player_id
        winner = event.winner_player_id
        if winner is None:
            continue
        if server == p1_id and winner in (p1_id, p2_id):
            p1_served += 1
            p1_won += 1 if winner == p1_id else 0
        elif server == p2_id and winner in (p1_id, p2_id):
            p2_served += 1
            p2_won += 1 if winner == p2_id else 0
    return ServeEvidence(
        p1_points_served=p1_served,
        p1_points_won=p1_won,
        p2_points_served=p2_served,
        p2_points_won=p2_won,
    )


def shrink_serve_prior(
    prior: float,
    *,
    served: int,
    won: int,
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> float:
    """Beta-binomial posterior mean with a fixed prior pseudo-sample size."""
    if served <= 0:
        return prior
    return (won + prior_strength * prior) / (served + prior_strength)


class LiveServeEstimator:
    def __init__(self, prior_strength: float = DEFAULT_PRIOR_STRENGTH) -> None:
        self._strength = prior_strength

    def estimate(
        self, prior: ServePointPrior, evidence: ServeEvidence
    ) -> ServePointPrior:
        return ServePointPrior(
            p1_serve_win=shrink_serve_prior(
                prior.p1_serve_win,
                served=evidence.p1_points_served,
                won=evidence.p1_points_won,
                prior_strength=self._strength,
            ),
            p2_serve_win=shrink_serve_prior(
                prior.p2_serve_win,
                served=evidence.p2_points_served,
                won=evidence.p2_points_won,
                prior_strength=self._strength,
            ),
        )
