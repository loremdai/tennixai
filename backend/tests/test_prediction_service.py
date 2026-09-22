"""PredictionService coverage, degradation and fail-closed tests (T62)."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain import (
    CircuitTier,
    DataFreshness,
    Discipline,
    Gender,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatus,
    Player,
    PointEvent,
    SetScore,
    Tournament,
)
from app.prediction.calibration import PlattCalibrator
from app.prediction.data import HistoricalMatch
from app.prediction.models import ModelAvailability
from app.prediction.prematch import EloCandidate
from app.prediction.service import PredictionService

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def build_artifact(
    directory: Path, *, promoted: bool = True, tamper: bool = False
) -> Path:
    from datetime import date, timedelta

    directory.mkdir(parents=True, exist_ok=True)
    players = [f"PLR_{i:03d}" for i in range(8)]
    matches = []
    for index in range(80):
        a = players[index % 8]
        b = players[(index + 3) % 8]
        matches.append(
            HistoricalMatch(
                match_key=f"art_{index:03d}",
                date=date(2024, 1, 1) + timedelta(days=index),
                tour="atp",
                surface="hard",
                format="best_of_3",
                player_a=a,
                player_b=b,
                winner="a" if index % 3 else "b",
            )
        )
    candidate = EloCandidate()
    candidate.fit(tuple(matches))
    candidate.save(directory)

    calibrator = PlattCalibrator()
    calibrator.fit([0.2, 0.4, 0.5, 0.6, 0.8], [0, 0, 1, 1, 1])
    calibrator.save(directory / "calibrator.joblib")

    (directory / "feature-schema.json").write_text(
        json.dumps({"version": "prematch-features-v1", "features": []}),
        encoding="utf-8",
    )
    card = {
        "card_version": "p3-model-card-v1",
        "source_id": "test-source",
        "license_id": "test-license",
        "code_version": "test",
        "windows": {
            "train": ["2024-01-01", "2024-02-01"],
            "validation": ["2024-02-02", "2024-02-20"],
            "test": ["2024-02-21", "2024-03-20"],
        },
        "champion": {"name": "surface_elo", "version": "elo-v1"},
        "calibration": {"selected": "platt"},
        "metrics": {"log_loss": 0.6},
        "subgroups": {},
        "promotion": {"result": "promoted" if promoted else "not_promoted"},
    }
    (directory / "model-card.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8"
    )

    files = {}
    for name in (
        "model.joblib",
        "calibrator.joblib",
        "feature-schema.json",
        "model-card.json",
    ):
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        files[name] = {"sha256": digest, "bytes": (directory / name).stat().st_size}
    (directory / "manifest.json").write_text(
        json.dumps({"manifest_version": "p3-manifest-v1", "files": files}),
        encoding="utf-8",
    )

    if tamper:
        model_path = directory / "model.joblib"
        model_path.write_bytes(model_path.read_bytes() + b"tampered")
    return directory


@pytest.fixture()
def artifact_dir(tmp_path) -> Path:
    return build_artifact(tmp_path / "artifact")


def make_match(
    *,
    circuit: CircuitTier = CircuitTier.ATP,
    discipline: Discipline = Discipline.SINGLES,
    status: MatchStatus = MatchStatus.SCHEDULED,
    live_state: LiveMatchState | None = None,
    match_format: str | None = "3",
    surface: str | None = "hard",
) -> Match:
    return Match(
        id="mat_1",
        status=status,
        players=(
            Player(id="ply_a", name="Alpha One"),
            Player(id="ply_b", name="Beta Two"),
        ),
        tournament=Tournament(
            id="trn_1",
            name="Test Open",
            tour="atp" if circuit is CircuitTier.ATP else "wta",
            circuit=circuit,
            gender=Gender.MEN,
            discipline=discipline,
        ),
        scheduled_at=NOW,
        surface=surface,
        format=match_format,
        live_state=live_state,
        freshness=DataFreshness(provider="test", observed_at=NOW),
    )


def make_snapshot(
    match: Match, *, points: tuple[PointEvent, ...] = ()
) -> MatchSnapshot:
    version = match.live_state.state_version if match.live_state else 0
    return MatchSnapshot(
        match=match,
        points=points,
        state_version=version,
        as_of=NOW,
    )


def live_state(
    *,
    sets_won=(0, 0),
    games=(3, 2),
    points=("30", "15"),
    server: str | None = "ply_a",
    version: int = 5,
) -> LiveMatchState:
    return LiveMatchState(
        score=MatchScore(
            sets_won=sets_won,
            sets=(SetScore(number=1, player1_games=games[0], player2_games=games[1]),),
            points=points,
        ),
        server_player_id=server,
        state_version=version,
        connection_status="live",  # type: ignore[arg-type]
    )


def pbp_points(*, p1_wins: int, p2_wins: int) -> tuple[PointEvent, ...]:
    events = []
    sequence = 1
    for _ in range(p1_wins):
        events.append(
            PointEvent(
                id=f"pe_{sequence}",
                match_id="mat_1",
                sequence=sequence,
                set_number=1,
                game_number=1,
                point_number=sequence,
                server_player_id="ply_a",
                winner_player_id="ply_a",
                score_after=MatchScore(sets_won=(0, 0), sets=(), points=("0", "0")),
                observed_at=NOW,
                provider="test",
                source_fingerprint=f"fp_{sequence}",
            )
        )
        sequence += 1
    for _ in range(p2_wins):
        events.append(
            PointEvent(
                id=f"pe_{sequence}",
                match_id="mat_1",
                sequence=sequence,
                set_number=1,
                game_number=1,
                point_number=sequence,
                server_player_id="ply_a",
                winner_player_id="ply_b",
                score_after=MatchScore(sets_won=(0, 0), sets=(), points=("0", "0")),
                observed_at=NOW,
                provider="test",
                source_fingerprint=f"fp_{sequence}",
            )
        )
        sequence += 1
    return tuple(events)


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_prematch_main_tour_singles_is_available(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    snapshot = make_snapshot(make_match())

    prediction = service.predict(snapshot)

    assert prediction.availability is ModelAvailability.AVAILABLE
    assert prediction.match_id == "mat_1"
    first, second = prediction.outcomes
    assert first.player_id == "ply_a"
    assert second.player_id == "ply_b"
    assert first.probability + second.probability == pytest.approx(1.0)
    assert prediction.model_version == "surface_elo:elo-v1"
    assert prediction.calibration_version == "platt"
    assert prediction.data_version
    assert prediction.input_state_version == snapshot.state_version
    assert {item.code for item in prediction.evidence} >= {"prematch_elo"}


def test_wta_main_tour_is_also_covered(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    snapshot = make_snapshot(make_match(circuit=CircuitTier.WTA))

    assert service.predict(snapshot).availability is ModelAvailability.AVAILABLE


@pytest.mark.parametrize(
    ("circuit", "discipline"),
    [
        (CircuitTier.CHALLENGER, Discipline.SINGLES),
        (CircuitTier.ITF, Discipline.SINGLES),
        (CircuitTier.ATP, Discipline.DOUBLES),
        (CircuitTier.OTHER, Discipline.SINGLES),
    ],
)
def test_out_of_domain_abstains_with_typed_reason(artifact_dir, circuit, discipline):
    service = PredictionService(artifact_dir=artifact_dir)
    snapshot = make_snapshot(make_match(circuit=circuit, discipline=discipline))

    prediction = service.predict(snapshot)

    assert prediction.availability is ModelAvailability.UNAVAILABLE
    assert prediction.abstain_reason == "OUT_OF_DOMAIN"
    assert prediction.outcomes == ()


# ---------------------------------------------------------------------------
# Promotion and artifact fail-closed
# ---------------------------------------------------------------------------


def test_missing_artifact_stays_unpromoted(tmp_path):
    service = PredictionService(artifact_dir=None)
    prediction = service.predict(make_snapshot(make_match()))

    assert prediction.availability is ModelAvailability.UNPROMOTED
    assert prediction.abstain_reason == "MODEL_UNPROMOTED"


def test_unpromoted_card_never_produces_probabilities(tmp_path):
    artifact = build_artifact(tmp_path / "a", promoted=False)
    service = PredictionService(artifact_dir=artifact)

    prediction = service.predict(make_snapshot(make_match()))

    assert prediction.availability is ModelAvailability.UNPROMOTED
    assert prediction.abstain_reason == "PROMOTION_NOT_GRANTED"
    assert prediction.outcomes == ()


def test_tampered_artifact_fails_closed(tmp_path):
    artifact = build_artifact(tmp_path / "a", tamper=True)
    service = PredictionService(artifact_dir=artifact)

    prediction = service.predict(make_snapshot(make_match()))

    assert prediction.availability is ModelAvailability.UNPROMOTED
    assert prediction.abstain_reason == "ARTIFACT_INVALID"
    assert prediction.outcomes == ()


def test_model_status_reports_the_deployment_truth_without_predicting(tmp_path):
    """The empty-state reason must not wait for a prediction to exist: the
    deployment either holds a promoted artifact or it does not."""
    assert PredictionService(artifact_dir=None).model_status() == "not_promoted"
    assert (
        PredictionService(artifact_dir=build_artifact(tmp_path / "p")).model_status()
        == "promoted"
    )
    assert (
        PredictionService(
            artifact_dir=build_artifact(tmp_path / "u", promoted=False)
        ).model_status()
        == "not_promoted"
    )


# ---------------------------------------------------------------------------
# Live prediction and degradation
# ---------------------------------------------------------------------------


def test_live_with_full_state_produces_scoring_probability(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    match = make_match(
        status=MatchStatus.LIVE,
        live_state=live_state(sets_won=(1, 0), games=(4, 2), points=("40", "15")),
    )

    prediction = service.predict(make_snapshot(match))

    assert prediction.availability is ModelAvailability.AVAILABLE
    codes = {item.code for item in prediction.evidence}
    assert "live_scoring" in codes
    assert "live_shrinkage" in codes or "serve_prior_default" in codes
    first = prediction.outcomes[0]
    # One set up, 4-2 and serving at 40-15 must be strongly favorable.
    assert first.probability > 0.85
    assert first.lower <= first.probability <= first.upper


def test_live_without_format_abstains_instead_of_guessing(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    match = make_match(
        status=MatchStatus.LIVE,
        live_state=live_state(),
        match_format=None,
    )

    prediction = service.predict(make_snapshot(match))

    assert prediction.availability is ModelAvailability.UNAVAILABLE
    assert prediction.abstain_reason == "FORMAT_UNKNOWN"


def test_live_missing_server_degrades_to_score_only(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    match = make_match(
        status=MatchStatus.LIVE,
        live_state=live_state(server=None, sets_won=(1, 0), games=(4, 2)),
    )

    prediction = service.predict(make_snapshot(match))

    assert prediction.availability is ModelAvailability.DEGRADED
    assert prediction.abstain_reason is None
    assert len(prediction.outcomes) == 2
    codes = {item.code for item in prediction.evidence}
    assert "score_only_fallback" in codes


def test_live_missing_score_abstains(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    state = LiveMatchState(score=None, server_player_id="ply_a", state_version=3)
    match = make_match(status=MatchStatus.LIVE, live_state=state)

    prediction = service.predict(make_snapshot(match))

    assert prediction.availability is ModelAvailability.UNAVAILABLE
    assert prediction.abstain_reason == "DATA_INCOMPLETE"


def test_pbp_shrinkage_moves_live_probability_directionally(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    base = make_match(
        status=MatchStatus.LIVE,
        live_state=live_state(sets_won=(0, 0), games=(3, 3), points=("0", "0")),
    )

    dominant = service.predict(
        make_snapshot(base, points=pbp_points(p1_wins=40, p2_wins=8))
    )
    struggling = service.predict(
        make_snapshot(base, points=pbp_points(p1_wins=8, p2_wins=40))
    )

    assert dominant.availability is ModelAvailability.AVAILABLE
    assert struggling.availability is ModelAvailability.AVAILABLE
    assert dominant.outcomes[0].probability > struggling.outcomes[0].probability
    assert {item.code for item in dominant.evidence} >= {"live_shrinkage"}


def test_finished_match_reports_terminal_probability(artifact_dir):
    service = PredictionService(artifact_dir=artifact_dir)
    match = make_match(
        status=MatchStatus.FINISHED,
        live_state=live_state(sets_won=(2, 0), version=99),
    )

    prediction = service.predict(make_snapshot(match))

    assert prediction.availability is ModelAvailability.AVAILABLE
    assert prediction.outcomes[0].probability == pytest.approx(1.0)
    assert prediction.outcomes[1].probability == pytest.approx(0.0)


def test_service_module_never_imports_market_code():
    source = Path("app/prediction/service.py").read_text(encoding="utf-8")
    assert "app.markets" not in source
    live_source = Path("app/prediction/live.py").read_text(encoding="utf-8")
    assert "app.markets" not in live_source
    scoring_source = Path("app/prediction/scoring.py").read_text(encoding="utf-8")
    assert "app.markets" not in scoring_source
