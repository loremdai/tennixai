"""Gates for the versioned aggregate calibration document.

The document may only carry aggregates (schema, counts, priors, alpha,
scale); raw vendor rows, external IDs and credentials must never appear.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain import (
    DataFreshness,
    Discipline,
    Gender,
    CircuitTier,
    Match,
    MatchScore,
    MatchSnapshot,
    Player,
    PointEvent,
    Tournament,
)
from app.momentum import ALGORITHM_VERSION
from app.momentum.calibration import (
    MIN_DETERMINATE_POINTS,
    Calibration,
    CohortPrior,
    MatchSample,
    build_calibration_document,
    collect_samples,
    load_calibration,
    write_calibration_document,
)


def sample(cohort: tuple[str, str, str], server_won: list[bool]) -> MatchSample:
    return MatchSample(cohort=cohort, server_won=tuple(server_won))


def rich_samples() -> list[MatchSample]:
    rows: list[MatchSample] = []
    for index in range(24):
        pattern = [index % 3 != 0] * 40
        pattern[7] = not pattern[7]
        pattern[23] = not pattern[23]
        rows.append(sample(("atp", "men", "singles"), pattern))
        rows.append(sample(("wta", "women", "singles"), [index % 4 != 0] * 40))
    return rows


def test_build_document_is_aggregate_only():
    document = build_calibration_document(rich_samples(), generated_at="2026-09-09T00:00:00Z")
    text = json.dumps(document, ensure_ascii=False)

    assert document["schema_version"] == 1
    assert document["algorithm_version"] == ALGORITHM_VERSION
    assert document["generated_at"] == "2026-09-09T00:00:00Z"
    assert document["sample"]["matches_used"] == 48
    assert 0 < document["alpha"] < 1
    assert document["scale"] > 0
    assert 0.5 < document["global"]["serve_win_prior"] < 0.9
    assert document["global"]["prior_strength"] > 0
    assert document["fallback"] == {
        "strategy": "global_prior",
        "min_cohort_points": 500,
    }
    # No vendor rows, external identifiers or point-level payloads.
    for forbidden in ("event", "ply_", "mat_", "key", "payload", "http"):
        assert forbidden not in text


def test_sparse_cohorts_fall_back_to_global(tmp_path):
    samples = [*rich_samples(), sample(("itf", "men", "singles"), [True] * 30)]
    document = build_calibration_document(samples, generated_at="2026-09-09T00:00:00Z")
    assert "itf|men|singles" not in document["cohorts"]

    path = tmp_path / "calibration.json"
    write_calibration_document(document, path)
    loaded = load_calibration(path)
    assert loaded.prior_for(CircuitTier.ITF, Gender.MEN, Discipline.SINGLES) == loaded.global_prior
    assert loaded.prior_for(CircuitTier.ATP, Gender.MEN, Discipline.SINGLES) != loaded.global_prior


def test_unknown_cohort_uses_global_prior():
    loaded = Calibration(
        schema_version=1,
        algorithm_version=ALGORITHM_VERSION,
        generated_at="2026-09-09T00:00:00Z",
        alpha=0.2,
        scale=0.4,
        global_prior=CohortPrior(serve_win_prior=0.62, prior_strength=8.0, sample_points=9000),
        cohorts={"atp|men|singles": CohortPrior(0.64, 10.0, 4000)},
    )
    assert loaded.prior_for(CircuitTier.CHALLENGER, Gender.UNKNOWN, Discipline.DOUBLES) == (
        loaded.global_prior
    )


def test_alpha_selection_is_deterministic():
    first = build_calibration_document(rich_samples(), generated_at="2026-09-09T00:00:00Z")
    second = build_calibration_document(rich_samples(), generated_at="2026-09-09T00:00:00Z")
    assert first == second


def test_write_and_load_roundtrip(tmp_path):
    document = build_calibration_document(rich_samples(), generated_at="2026-09-09T00:00:00Z")
    path = tmp_path / "calibration.v1.json"
    write_calibration_document(document, path)

    loaded = load_calibration(path)
    assert loaded.schema_version == 1
    assert loaded.alpha == pytest.approx(document["alpha"])
    assert loaded.scale == pytest.approx(document["scale"])
    assert loaded.global_prior.serve_win_prior == pytest.approx(
        document["global"]["serve_win_prior"]
    )


def test_committed_calibration_file_is_valid_aggregate():
    loaded = load_calibration()
    assert loaded.schema_version == 1
    assert loaded.algorithm_version == ALGORITHM_VERSION
    assert 0 < loaded.alpha < 1
    assert loaded.scale > 0
    assert 0.5 < loaded.global_prior.serve_win_prior < 0.9
    assert loaded.global_prior.prior_strength > 0
    assert loaded.global_prior.sample_points >= MIN_DETERMINATE_POINTS
    for prior in loaded.cohorts.values():
        assert 0 < prior.serve_win_prior < 1
        assert prior.prior_strength > 0
        assert prior.sample_points >= MIN_DETERMINATE_POINTS


def test_calibration_module_runs_without_import_warning():
    result = subprocess.run(
        [sys.executable, "-m", "app.momentum.calibration", "--help"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "RuntimeWarning" not in result.stderr


class RecordingProvider:
    """Bounded stand-in for TennisDataProvider: counts every call."""

    def __init__(self, matches_per_player: int, determinate_points: int) -> None:
        self.matches_per_player = matches_per_player
        self.determinate_points = determinate_points
        self.fixture_calls = 0
        self.results_calls = 0
        self.snapshot_calls = 0

    def _match(self, index: int) -> Match:
        return Match(
            id=f"mat_{index}",
            status="finished",
            players=(
                Player(id=f"ply_{index}_a", name=f"Player A{index}"),
                Player(id=f"ply_{index}_b", name=f"Player B{index}"),
            ),
            tournament=Tournament(id="trn_1", name="ATP Finals"),
            winner_player_id=f"ply_{index}_a",
            freshness=DataFreshness(
                provider="fake",
                source_updated_at=None,
                observed_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
                is_stale=False,
                age_seconds=0,
            ),
        )

    def _snapshot(self, match: Match) -> MatchSnapshot:
        points = tuple(
            PointEvent(
                id=f"{match.id}_pe_{sequence}",
                match_id=match.id,
                sequence=sequence,
                set_number=1,
                game_number=1,
                point_number=sequence,
                server_player_id=match.players[sequence % 2].id,
                winner_player_id=match.players[(sequence + 1) % 2].id,
                score_after=MatchScore(sets_won=(0, 0), sets=(), points=("0", "0")),
                observed_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC) + timedelta(seconds=sequence),
                provider="fake",
                source_fingerprint=f"fp-{sequence}",
            )
            for sequence in range(1, self.determinate_points + 1)
        )
        return MatchSnapshot(
            match=match,
            points=points,
            statistics=(),
            momentum=(),
            quality=(),
            state_version=0,
            as_of=datetime(2026, 9, 1, 13, 0, tzinfo=UTC),
        )

    async def get_fixtures(self, *, player_id: str | None = None):
        self.fixture_calls += 1
        return [self._match(0), self._match(1)]

    async def get_recent_results(self, player_id: str, *, limit: int):
        self.results_calls += 1
        start = 100 + self.results_calls * self.matches_per_player
        return [
            self._match(start + index)
            for index in range(min(limit, self.matches_per_player))
        ]

    async def get_match_snapshot(self, match_id: str):
        self.snapshot_calls += 1
        return self._snapshot(self._match(int(match_id.split("_")[1])))


async def test_collect_samples_is_bounded_and_skips_thin_matches():
    provider = RecordingProvider(matches_per_player=30, determinate_points=40)
    samples = await collect_samples(provider, max_players=4, results_per_player=8, max_matches=10)

    assert len(samples) == 10
    assert provider.fixture_calls == 1
    assert provider.results_calls <= 4
    assert provider.snapshot_calls <= 10
    assert all(len(row.server_won) == 40 for row in samples)

    thin = RecordingProvider(matches_per_player=30, determinate_points=MIN_DETERMINATE_POINTS - 1)
    assert await collect_samples(thin, max_players=4, results_per_player=8, max_matches=10) == []
