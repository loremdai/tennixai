from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain import (
    DataFreshness,
    LiveMatchState,
    Match,
    MatchScore,
    MatchStatus,
    Player,
    SetScore,
    Tournament,
)


def test_freshness_requires_timezone_aware_datetimes() -> None:
    with pytest.raises(ValidationError):
        DataFreshness(provider="fake", observed_at=datetime(2026, 9, 8, 12, 0))

    value = DataFreshness(
        provider="fake",
        observed_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
    )
    assert value.is_stale is False


def test_freshness_rejects_naive_source_updated_at() -> None:
    with pytest.raises(ValidationError):
        DataFreshness(
            provider="fake",
            observed_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            source_updated_at=datetime(2026, 9, 8, 11, 0),
        )


def test_match_requires_timezone_aware_scheduled_at() -> None:
    players = (
        Player(id="ply_a", name="Jannik Sinner"),
        Player(id="ply_b", name="Carlos Alcaraz"),
    )
    tournament = Tournament(id="trn_a", name="ATP Finals")
    freshness = DataFreshness(
        provider="fake", observed_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    )

    with pytest.raises(ValidationError):
        Match(
            id="mat_a",
            status=MatchStatus.SCHEDULED,
            players=players,
            tournament=tournament,
            scheduled_at=datetime(2026, 9, 8, 12, 30),
            freshness=freshness,
        )

    match = Match(
        id="mat_a",
        status=MatchStatus.SCHEDULED,
        players=players,
        tournament=tournament,
        scheduled_at=datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc),
        freshness=freshness,
    )
    assert match.round is None
    assert match.surface is None
    assert match.live_state is None
    assert match.winner_player_id is None


def test_models_are_frozen_and_forbid_extra_fields() -> None:
    player = Player(id="ply_a", name="Jannik Sinner")

    with pytest.raises(ValidationError):
        player.name = "Other"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        Player(id="ply_a", name="Jannik Sinner, ", unknown_field="x")  # type: ignore[call-arg]


def test_live_match_state_defaults_and_score_shape() -> None:
    score = MatchScore(
        sets_won=(1, 1),
        sets=(
            SetScore(number=1, player1_games=6, player2_games=4),
            SetScore(number=2, player1_games=4, player2_games=6),
            SetScore(number=3, player1_games=4, player2_games=5),
        ),
        points=("30", "15"),
        is_tiebreak=False,
    )
    state = LiveMatchState(score=score, server_player_id="ply_a")

    assert state.score is not None
    assert state.score.sets[2].player2_games == 5
    assert state.server_player_id == "ply_a"

    empty = LiveMatchState()
    assert empty.score is None
    assert empty.server_player_id is None


def test_match_status_values() -> None:
    assert [status.value for status in MatchStatus] == [
        "scheduled",
        "live",
        "finished",
        "cancelled",
        "postponed",
        "unknown",
    ]
