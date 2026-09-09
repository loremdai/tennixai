"""Versioned aggregate calibration for the Recent Control Index v1.

The calibration command samples a bounded window of finished matches through
``TennisDataProvider``, keeps only per-point "did the server win" booleans in
memory, and writes an aggregate document: schema version, generation time,
sample counts, serve-win priors with strengths per cohort, the EWMA alpha and
the output scale. Raw vendor rows, external identifiers and credentials never
reach the document.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.config import Settings
from app.domain import CircuitTier, Discipline, Gender, MatchStatus
from app.momentum.engine import ALGORITHM_VERSION, Calibration, CohortPrior
from app.providers.base import TennisDataProvider

SCHEMA_VERSION = 1
DEFAULT_OUTPUT = Path(__file__).with_name("calibration.v1.json")

#: Matches with fewer determinate points cannot inform the calibration.
MIN_DETERMINATE_POINTS = 20
#: Cohorts below this sample size fall back to the global prior.
MIN_COHORT_POINTS = 500
CANDIDATE_HALF_LIVES = (3.0, 5.0, 8.0, 12.0, 20.0)


@dataclass(frozen=True)
class MatchSample:
    """One finished match reduced to its cohort and server-won booleans."""

    cohort: tuple[str, str, str]
    server_won: tuple[bool, ...]


def cohort_key(circuit: CircuitTier, gender: Gender, discipline: Discipline) -> str:
    return f"{circuit.value}|{gender.value}|{discipline.value}"


def _prior_strength(sample_points: int) -> float:
    return float(min(12, max(4, sample_points // 200)))


def _ewma_series(residuals: Sequence[float], alpha: float) -> list[float]:
    series: list[float] = []
    smoothed = 0.0
    for residual in residuals:
        smoothed = (1.0 - alpha) * smoothed + alpha * residual
        series.append(smoothed)
    return series


def _select_half_life(
    samples: Sequence[MatchSample], priors: Mapping[tuple[str, str, str], float], fallback: float
) -> tuple[float, float]:
    """Pick the EWMA half-life that moves on genuine swings without jitter.

    Responsiveness is the average late-half drift of each match series;
    jitter is the average step size over the same window. The best candidate
    maximises their ratio; ties prefer the smoother (smaller alpha) side.
    """

    usable = [row for row in samples if len(row.server_won) >= 12]
    residuals_by_match = [
        [2.0 * (1.0 if won else 0.0) - 2.0 * priors.get(row.cohort, fallback) for won in row.server_won]
        for row in usable
    ]
    best: tuple[float, float, float] | None = None
    for half_life in CANDIDATE_HALF_LIVES:
        alpha = math.log(2.0) / half_life
        drift = 0.0
        jitter = 0.0
        counted = 0
        for residuals in residuals_by_match:
            series = _ewma_series(residuals, alpha)
            half = len(series) // 2
            drift += abs(series[-1] - series[half])
            jitter += sum(abs(series[i] - series[i - 1]) for i in range(half + 1, len(series))) / max(
                1, len(series) - half - 1
            )
            counted += 1
        if not counted:
            continue
        drift /= counted
        jitter /= counted
        if jitter <= 0:
            continue
        score = drift / jitter
        if best is None or score > best[0] + 1e-12:
            best = (score, alpha, half_life)
    if best is None:
        return math.log(2.0) / 8.0, 8.0
    return best[1], best[2]


def build_calibration_document(samples: Sequence[MatchSample], *, generated_at: str) -> dict:
    counts: dict[tuple[str, str, str], list[int]] = {}
    total_points = 0
    total_wins = 0
    for row in samples:
        wins = sum(1 for won in row.server_won if won)
        bucket = counts.setdefault(row.cohort, [0, 0])
        bucket[0] += len(row.server_won)
        bucket[1] += wins
        total_points += len(row.server_won)
        total_wins += wins

    global_prior = CohortPrior(
        serve_win_prior=round(total_wins / total_points, 4) if total_points else 0.6,
        prior_strength=_prior_strength(total_points),
        sample_points=total_points,
    )
    cohorts = {
        "|".join(key): CohortPrior(
            serve_win_prior=round(wins / points, 4),
            prior_strength=_prior_strength(points),
            sample_points=points,
        )
        for key, (points, wins) in sorted(counts.items())
        if points >= MIN_COHORT_POINTS
    }
    cohort_means = {
        key: prior.serve_win_prior
        for key, prior in (
            (tuple(part for part in joined.split("|")), prior)
            for joined, prior in cohorts.items()
        )
    }
    alpha, half_life = _select_half_life(samples, cohort_means, global_prior.serve_win_prior)

    magnitudes: list[float] = []
    for row in samples:
        mean = cohort_means.get(row.cohort, global_prior.serve_win_prior)
        residuals = [2.0 * (1.0 if won else 0.0) - 2.0 * mean for won in row.server_won]
        magnitudes.extend(abs(value) for value in _ewma_series(residuals, alpha))
    magnitudes.sort()
    if magnitudes:
        scale = round(magnitudes[min(len(magnitudes) - 1, int(0.9 * len(magnitudes)))], 4) or 1.0
    else:
        scale = 1.0

    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": generated_at,
        "sample": {
            "matches_used": len(samples),
            "determinate_points": total_points,
        },
        "global": {
            "serve_win_prior": global_prior.serve_win_prior,
            "prior_strength": global_prior.prior_strength,
            "sample_points": global_prior.sample_points,
        },
        "cohorts": {
            key: {
                "serve_win_prior": prior.serve_win_prior,
                "prior_strength": prior.prior_strength,
                "sample_points": prior.sample_points,
            }
            for key, prior in cohorts.items()
        },
        "fallback": {
            "strategy": "global_prior",
            "min_cohort_points": MIN_COHORT_POINTS,
        },
        "half_life_points": half_life,
        "alpha": round(alpha, 6),
        "scale": scale,
    }


def write_calibration_document(document: dict, path: Path) -> None:
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_calibration(path: Path | None = None) -> Calibration:
    source = path or DEFAULT_OUTPUT
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported calibration schema: {raw.get('schema_version')}")
    if raw.get("algorithm_version") != ALGORITHM_VERSION:
        raise ValueError(f"unsupported algorithm version: {raw.get('algorithm_version')}")
    return Calibration(
        schema_version=SCHEMA_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        generated_at=raw["generated_at"],
        alpha=float(raw["alpha"]),
        scale=float(raw["scale"]),
        global_prior=CohortPrior(
            serve_win_prior=float(raw["global"]["serve_win_prior"]),
            prior_strength=float(raw["global"]["prior_strength"]),
            sample_points=int(raw["global"]["sample_points"]),
        ),
        cohorts={
            key: CohortPrior(
                serve_win_prior=float(entry["serve_win_prior"]),
                prior_strength=float(entry["prior_strength"]),
                sample_points=int(entry["sample_points"]),
            )
            for key, entry in raw.get("cohorts", {}).items()
        },
    )


async def collect_samples(
    provider: TennisDataProvider,
    *,
    max_players: int,
    results_per_player: int,
    max_matches: int,
) -> list[MatchSample]:
    """Bounded recent sample: today's fixtures seed players, then per-player
    recent results seed finished matches. Call counts stay capped."""

    fixtures = await provider.get_fixtures()
    player_ids: list[str] = []
    for match in fixtures:
        for player in match.players:
            if player.id not in player_ids:
                player_ids.append(player.id)
            if len(player_ids) >= max_players:
                break
        if len(player_ids) >= max_players:
            break

    candidates: dict[str, object] = {}
    for player_id in player_ids:
        results = await provider.get_recent_results(player_id, limit=results_per_player)
        for match in results:
            if match.status is MatchStatus.FINISHED and match.id not in candidates:
                candidates[match.id] = match

    samples: list[MatchSample] = []
    for match in candidates.values():
        if len(samples) >= max_matches:
            break
        snapshot = await provider.get_match_snapshot(match.id)
        determinate = sorted(
            (
                point
                for point in snapshot.points
                if point.winner_player_id is not None and point.server_player_id is not None
            ),
            key=lambda point: point.sequence,
        )
        if len(determinate) < MIN_DETERMINATE_POINTS:
            continue
        tournament = snapshot.match.tournament
        samples.append(
            MatchSample(
                cohort=(
                    tournament.circuit.value,
                    tournament.gender.value,
                    tournament.discipline.value,
                ),
                server_won=tuple(
                    point.winner_player_id == point.server_player_id for point in determinate
                ),
            )
        )
    return samples


async def _run(args: argparse.Namespace) -> None:
    import httpx

    from app.identity import MemoryIdentityRepository
    from app.providers.api_tennis import ApiTennisProvider
    from app.providers.fake import FakeTennisProvider

    settings = Settings()
    clock = lambda: datetime.now(UTC)  # noqa: E731 - calibration stamps are wall clock
    client: httpx.AsyncClient | None = None
    if settings.provider_mode == "api_tennis":
        api_key = settings.api_tennis_api_key
        if api_key is None:
            raise ValueError("TENNIX_API_TENNIS_API_KEY is required to calibrate from live data")
        client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=15.0)
        provider: TennisDataProvider = ApiTennisProvider(
            client=client,
            identities=MemoryIdentityRepository(),
            api_key=api_key.get_secret_value(),
            now=clock,
        )
    else:
        provider = FakeTennisProvider(identities=MemoryIdentityRepository(), now=clock)

    try:
        samples = await collect_samples(
            provider,
            max_players=args.max_players,
            results_per_player=args.results_per_player,
            max_matches=args.max_matches,
        )
    finally:
        if client is not None:
            await client.aclose()

    if not samples:
        raise SystemExit("no usable determinate samples collected; document not written")
    document = build_calibration_document(
        samples,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    document["sample"]["window_days"] = args.days
    write_calibration_document(document, Path(args.output))
    print(
        f"wrote {args.output}: matches={document['sample']['matches_used']} "
        f"points={document['sample']['determinate_points']} alpha={document['alpha']} "
        f"scale={document['scale']} cohorts={len(document['cohorts'])}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate the Recent Control Index v1")
    parser.add_argument("--days", type=int, default=30, help="documented sampling window label")
    parser.add_argument("--max-matches", type=int, default=200)
    parser.add_argument("--max-players", type=int, default=16)
    parser.add_argument("--results-per-player", type=int, default=20)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
