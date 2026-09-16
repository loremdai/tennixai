"""Runtime prediction facade (T62).

Turns a canonical MatchSnapshot into a calibrated PredictionSnapshot or a
typed abstention. Coverage is main-tour singles only; Challenger/ITF and
doubles abstain OUT_OF_DOMAIN. Model artifacts load fail-closed: a missing,
tampered or unpromoted artifact never produces probabilities. This module
reads tennis data only and must never import market code.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import joblib

from app.domain import CircuitTier, Discipline, MatchSnapshot, MatchStatus
from app.prediction.calibration import (
    BaseCalibrator,
    BetaCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
)
from app.prediction.data import HistoricalMatch
from app.prediction.live import LiveServeEstimator, count_service_points
from app.prediction.models import (
    ModelAvailability,
    PredictionEvidence,
    PredictionSnapshot,
    ProbabilityEstimate,
)
from app.prediction.prematch import EloCandidate, EloState
from app.prediction.scoring import (
    ScoringFormatUnknown,
    ScoringProbabilityEngine,
    ServePointPrior,
    TennisScoringState,
)

DATA_VERSION = "canonical-snapshot-v1"
DEFAULT_SERVE_PRIOR = ServePointPrior(p1_serve_win=0.64, p2_serve_win=0.64)
COVERED_CIRCUITS = frozenset({CircuitTier.ATP, CircuitTier.WTA})
POINT_TEXT_TO_INDEX = {
    "0": 0,
    "15": 1,
    "30": 2,
    "40": 3,
    "a": 4,
    "adv": 4,
    "45": 4,
}
FORMAT_ALIASES = {
    "3": 3,
    "5": 5,
    "bo3": 3,
    "bo5": 5,
    "best_of_3": 3,
    "best_of_5": 5,
    "bestof3": 3,
    "bestof5": 5,
}
CALIBRATOR_CLASSES = {
    "platt": PlattCalibrator,
    "beta": BetaCalibrator,
    "isotonic": IsotonicCalibrator,
}

_PREMATCH_HALF_WIDTH = 0.05
_LIVE_HALF_WIDTH = 0.07
_DEGRADED_HALF_WIDTH = 0.12


class ArtifactInvalid(Exception):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


class PredictionArtifact:
    """A verified, promoted model artifact bundle."""

    def __init__(
        self,
        *,
        model_version: str,
        calibration_version: str,
        calibrator: BaseCalibrator,
        elo_state: EloState,
    ) -> None:
        self.model_version = model_version
        self.calibration_version = calibration_version
        self.calibrator = calibrator
        self.elo_state = elo_state

    @classmethod
    def load(cls, directory: Path | str) -> "PredictionArtifact":
        directory = Path(directory)
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            raise ArtifactInvalid("ARTIFACT_INVALID", "manifest missing")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ArtifactInvalid("ARTIFACT_INVALID", "manifest unreadable") from exc
        for name, entry in manifest.get("files", {}).items():
            path = directory / name
            if not path.is_file():
                raise ArtifactInvalid("ARTIFACT_INVALID", f"{name} missing")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry.get("sha256"):
                raise ArtifactInvalid("ARTIFACT_INVALID", f"{name} hash mismatch")

        card_path = directory / "model-card.json"
        if not card_path.is_file():
            raise ArtifactInvalid("ARTIFACT_INVALID", "model card missing")
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ArtifactInvalid("ARTIFACT_INVALID", "model card unreadable") from exc
        promotion = (card.get("promotion") or {}).get("result")
        if promotion != "promoted":
            raise ArtifactInvalid("PROMOTION_NOT_GRANTED", "model card is not promoted")
        champion = card.get("champion") or {}
        if champion.get("name") != "surface_elo":
            raise ArtifactInvalid(
                "CHAMPION_UNSUPPORTED",
                "runtime only loads the audited surface_elo champion",
            )

        model_payload = joblib.load(directory / "model.joblib")
        if model_payload.get("kind") != "surface_elo":
            raise ArtifactInvalid("ARTIFACT_INVALID", "model payload mismatch")
        elo_state = EloState(
            overall=dict(model_payload.get("overall", {})),
            surface={
                surface: dict(values)
                for surface, values in model_payload.get("surface", {}).items()
            },
        )

        calibration_name = (card.get("calibration") or {}).get("selected", "platt")
        calibrator_class = CALIBRATOR_CLASSES.get(calibration_name)
        if calibrator_class is None:
            raise ArtifactInvalid(
                "ARTIFACT_INVALID", f"unknown calibrator {calibration_name}"
            )
        calibrator_payload = joblib.load(directory / "calibrator.joblib")
        calibrator = calibrator_class()
        calibrator.__dict__.update(calibrator_payload.get("state", {}))

        return cls(
            model_version=f"{champion.get('name')}:{champion.get('version')}",
            calibration_version=calibration_name,
            calibrator=calibrator,
            elo_state=elo_state,
        )


class PredictionService:
    def __init__(
        self,
        *,
        artifact_dir: Path | str | None = None,
        engine: ScoringProbabilityEngine | None = None,
        serve_prior: ServePointPrior = DEFAULT_SERVE_PRIOR,
        prior_strength: float = 25.0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._artifact_dir = Path(artifact_dir) if artifact_dir else None
        self._artifact: PredictionArtifact | None = None
        self._artifact_error: ArtifactInvalid | None = None
        self._engine = engine or ScoringProbabilityEngine()
        self._serve_prior = serve_prior
        self._estimator = LiveServeEstimator(prior_strength=prior_strength)
        self._now = now_fn or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------

    def predict(self, snapshot: MatchSnapshot) -> PredictionSnapshot:
        match = snapshot.match

        if (
            match.tournament.circuit not in COVERED_CIRCUITS
            or match.tournament.discipline is not Discipline.SINGLES
        ):
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "OUT_OF_DOMAIN"
            )

        artifact = self._load_artifact()
        if isinstance(artifact, ArtifactInvalid):
            return self._abstain(
                snapshot, ModelAvailability.UNPROMOTED, artifact.reason_code
            )
        if artifact is None:
            return self._abstain(
                snapshot, ModelAvailability.UNPROMOTED, "MODEL_UNPROMOTED"
            )

        status = match.status
        live_state = match.live_state
        if status is MatchStatus.SCHEDULED:
            return self._predict_prematch(snapshot, artifact)
        if status is MatchStatus.FINISHED:
            return self._predict_terminal(snapshot, artifact)
        if status in (MatchStatus.CANCELLED, MatchStatus.POSTPONED):
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "MATCH_NOT_PLAYABLE"
            )
        if live_state is None or live_state.score is None:
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "DATA_INCOMPLETE"
            )
        return self._predict_live(snapshot, artifact)

    # ------------------------------------------------------------------

    def _load_artifact(self) -> PredictionArtifact | ArtifactInvalid | None:
        if self._artifact_dir is None:
            return None
        if self._artifact is not None:
            return self._artifact
        if self._artifact_error is not None:
            return self._artifact_error
        try:
            self._artifact = PredictionArtifact.load(self._artifact_dir)
        except ArtifactInvalid as error:
            self._artifact_error = error
        return self._artifact or self._artifact_error

    def _abstain(
        self,
        snapshot: MatchSnapshot,
        availability: ModelAvailability,
        reason: str,
    ) -> PredictionSnapshot:
        return PredictionSnapshot(
            match_id=snapshot.match.id,
            outcomes=(),
            availability=availability,
            abstain_reason=reason,
            model_version=self._model_version_or("unpromoted"),
            calibration_version=self._calibration_version_or("none"),
            data_version=DATA_VERSION,
            input_state_version=snapshot.state_version,
            as_of=snapshot.as_of,
        )

    def _model_version_or(self, fallback: str) -> str:
        return self._artifact.model_version if self._artifact else fallback

    def _calibration_version_or(self, fallback: str) -> str:
        return self._artifact.calibration_version if self._artifact else fallback

    def _build(
        self,
        snapshot: MatchSnapshot,
        artifact: PredictionArtifact,
        raw_probability: float,
        *,
        availability: ModelAvailability,
        evidence: tuple[PredictionEvidence, ...],
        half_width: float,
    ) -> PredictionSnapshot:
        terminal = raw_probability <= 1e-12 or raw_probability >= 1 - 1e-12
        if terminal:
            calibrated = 1.0 if raw_probability >= 0.5 else 0.0
        else:
            calibrated = float(
                artifact.calibrator.predict(
                    [min(max(raw_probability, 1e-6), 1 - 1e-6)]
                )[0]
            )
            calibrated = min(max(calibrated, 1e-6), 1 - 1e-6)
        complement = 1.0 - calibrated
        players = snapshot.match.players
        return PredictionSnapshot(
            match_id=snapshot.match.id,
            outcomes=(
                ProbabilityEstimate(
                    player_id=players[0].id,
                    probability=calibrated,
                    lower=max(0.0, calibrated - half_width),
                    upper=min(1.0, calibrated + half_width),
                ),
                ProbabilityEstimate(
                    player_id=players[1].id,
                    probability=complement,
                    lower=max(0.0, complement - half_width),
                    upper=min(1.0, complement + half_width),
                ),
            ),
            availability=availability,
            model_version=artifact.model_version,
            calibration_version=artifact.calibration_version,
            data_version=DATA_VERSION,
            input_state_version=snapshot.state_version,
            evidence=evidence,
            as_of=snapshot.as_of,
        )

    # ------------------------------------------------------------------

    def _predict_prematch(
        self, snapshot: MatchSnapshot, artifact: PredictionArtifact
    ) -> PredictionSnapshot:
        match = snapshot.match
        when = (match.scheduled_at or snapshot.as_of).date()
        query = HistoricalMatch(
            match_key=match.id,
            date=when,
            tour=match.tournament.tour or "atp",
            surface=match.surface or "unknown",
            format=match.format or "unknown",
            player_a=match.players[0].id,
            player_b=match.players[1].id,
            winner="a",  # never used for inference
        )
        raw = EloCandidate().predict_before(artifact.elo_state, query)
        evidence = [
            PredictionEvidence(
                code="prematch_elo",
                description="Surface-aware Elo rating difference",
                value=raw,
            )
        ]
        if match.surface:
            evidence.append(
                PredictionEvidence(
                    code="surface_rating",
                    description=f"Surface component for {match.surface}",
                )
            )
        return self._build(
            snapshot,
            artifact,
            raw,
            availability=ModelAvailability.AVAILABLE,
            evidence=tuple(evidence),
            half_width=_PREMATCH_HALF_WIDTH,
        )

    def _predict_terminal(
        self, snapshot: MatchSnapshot, artifact: PredictionArtifact
    ) -> PredictionSnapshot:
        match = snapshot.match
        live_state = match.live_state
        if live_state is not None and live_state.score is not None:
            sets = live_state.score.sets_won
            if sets[0] > sets[1]:
                raw = 1.0
            elif sets[1] > sets[0]:
                raw = 0.0
            else:
                raw = None
        else:
            raw = None
        if raw is None and match.winner_player_id is not None:
            raw = 1.0 if match.winner_player_id == match.players[0].id else 0.0
        if raw is None:
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "DATA_INCOMPLETE"
            )
        return self._build(
            snapshot,
            artifact,
            raw,
            availability=ModelAvailability.AVAILABLE,
            evidence=(
                PredictionEvidence(
                    code="terminal_result",
                    description="Match finished; probability is the result",
                ),
            ),
            half_width=0.0,
        )

    def _predict_live(
        self, snapshot: MatchSnapshot, artifact: PredictionArtifact
    ) -> PredictionSnapshot:
        match = snapshot.match
        live_state = match.live_state
        assert live_state is not None and live_state.score is not None  # noqa: S101
        score = live_state.score

        best_of = FORMAT_ALIASES.get((match.format or "").strip().lower())
        if best_of is None:
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "FORMAT_UNKNOWN"
            )

        sets_won = score.sets_won
        games = self._current_games(score)

        evidence_points = snapshot.points
        serve = self._serve_prior
        evidence: list[PredictionEvidence] = []
        if evidence_points:
            counted = count_service_points(
                evidence_points,
                up_to_sequence=10**9,
                p1_id=match.players[0].id,
                p2_id=match.players[1].id,
            )
            if counted.p1_points_served + counted.p2_points_served > 0:
                serve = self._estimator.estimate(serve, counted)
                evidence.append(
                    PredictionEvidence(
                        code="live_shrinkage",
                        description=(
                            "Serve priors shrunk with in-match service points"
                        ),
                        value=float(
                            counted.p1_points_served + counted.p2_points_served
                        ),
                    )
                )
        if not any(item.code == "live_shrinkage" for item in evidence):
            evidence.append(
                PredictionEvidence(
                    code="serve_prior_default",
                    description="Tour-average serve prior; no usable PBP evidence",
                )
            )

        server_index: int | None = None
        if live_state.server_player_id == match.players[0].id:
            server_index = 0
        elif live_state.server_player_id == match.players[1].id:
            server_index = 1

        if server_index is None:
            # Score-only fallback: no server, no point-level state.
            mean_prior = (serve.p1_serve_win + serve.p2_serve_win) / 2
            symmetric = ServePointPrior(mean_prior, mean_prior)
            state = TennisScoringState(
                sets_won=sets_won,
                games_in_current_set=games,
                points_in_current_game=(0, 0),
                server=0,
                is_tiebreak=games == (6, 6),
                best_of=best_of,
            )
            raw = self._engine.match_win_probability(state, symmetric)
            evidence.append(
                PredictionEvidence(
                    code="score_only_fallback",
                    description="Server unknown; sets/games state with symmetric prior",
                )
            )
            evidence.append(
                PredictionEvidence(code="live_scoring", description="Scoring DP")
            )
            return self._build(
                snapshot,
                artifact,
                raw,
                availability=ModelAvailability.DEGRADED,
                evidence=tuple(evidence),
                half_width=_DEGRADED_HALF_WIDTH,
            )

        points = self._parse_points(score.points)
        if points is None:
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "DATA_INCOMPLETE"
            )
        state = TennisScoringState(
            sets_won=sets_won,
            games_in_current_set=games,
            points_in_current_game=points,
            server=server_index,
            is_tiebreak=bool(score.is_tiebreak) or games == (6, 6),
            best_of=best_of,
        )
        try:
            raw = self._engine.match_win_probability(state, serve)
        except ScoringFormatUnknown:
            return self._abstain(
                snapshot, ModelAvailability.UNAVAILABLE, "FORMAT_UNKNOWN"
            )
        evidence.append(
            PredictionEvidence(code="live_scoring", description="Scoring DP")
        )
        return self._build(
            snapshot,
            artifact,
            raw,
            availability=ModelAvailability.AVAILABLE,
            evidence=tuple(evidence),
            half_width=_LIVE_HALF_WIDTH,
        )

    @staticmethod
    def _current_games(score) -> tuple[int, int]:
        completed = sum(score.sets_won)
        rows = list(score.sets)
        if rows and len(rows) > completed:
            current = rows[-1]
            return (
                current.player1_games or 0,
                current.player2_games or 0,
            )
        return (0, 0)

    @staticmethod
    def _parse_points(points: tuple[str | None, str | None]) -> tuple[int, int] | None:
        first_raw, second_raw = points
        if first_raw is None and second_raw is None:
            return (0, 0)
        if first_raw is None or second_raw is None:
            return None
        first = POINT_TEXT_TO_INDEX.get(str(first_raw).strip().lower())
        second = POINT_TEXT_TO_INDEX.get(str(second_raw).strip().lower())
        if first is None or second is None:
            return None
        return (first, second)
