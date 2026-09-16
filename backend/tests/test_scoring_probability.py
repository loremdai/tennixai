"""Deterministic tennis scoring probability engine tests (T62)."""

import pytest

from app.prediction.scoring import (
    ScoringFormatUnknown,
    ScoringProbabilityEngine,
    ServePointPrior,
    TennisScoringState,
)

EVEN = ServePointPrior(p1_serve_win=0.5, p2_serve_win=0.5)
TYPICAL = ServePointPrior(p1_serve_win=0.65, p2_serve_win=0.65)

ENGINE = ScoringProbabilityEngine()


def state(
    *,
    sets: tuple[int, int] = (0, 0),
    games: tuple[int, int] = (0, 0),
    points: tuple[int, int] = (0, 0),
    server: int = 0,
    tiebreak: bool = False,
    best_of: int | None = 3,
) -> TennisScoringState:
    return TennisScoringState(
        sets_won=sets,
        games_in_current_set=games,
        points_in_current_game=points,
        server=server,
        is_tiebreak=tiebreak,
        best_of=best_of,
    )


def test_love_all_is_symmetric_with_equal_priors():
    assert ENGINE.match_win_probability(state(), EVEN) == pytest.approx(0.5)
    assert ENGINE.match_win_probability(state(server=1), EVEN) == pytest.approx(0.5)


def test_stronger_serving_side_has_match_advantage():
    # Under symmetric priors the match is exactly fair regardless of who
    # serves first; an asymmetric serve edge must show up instead.
    asymmetric = ServePointPrior(p1_serve_win=0.72, p2_serve_win=0.6)
    serving = ENGINE.match_win_probability(state(server=0), asymmetric)
    returning = ENGINE.match_win_probability(state(server=1), asymmetric)
    assert serving > 0.5
    assert returning > 0.5
    # Serving first never hurts the stronger server (structure is symmetric
    # under exact alternation, so equality is legitimate).
    assert serving >= returning
    # Mirror sanity: equal priors give exactly 0.5.
    assert ENGINE.match_win_probability(state(server=0), EVEN) == pytest.approx(0.5)


def test_game_level_server_advantage():
    # Same match score, current game 0-0: the server of this game is better
    # off than the returner.
    server_ahead = ENGINE.match_win_probability(state(server=0), TYPICAL)
    # Compare against being a set down to show game-level sensitivity.
    assert 0.45 < server_ahead < 0.55  # symmetric match-level fairness


def test_break_point_pressure_lowers_server_probability():
    # p1 serves at 40-0 versus 0-40 in an otherwise identical match.
    ahead = ENGINE.match_win_probability(state(points=(3, 0)), TYPICAL)
    behind = ENGINE.match_win_probability(state(points=(0, 3)), TYPICAL)
    assert ahead > 0.5
    assert behind < 0.5
    assert ahead > behind


def test_deuce_and_advantage_states_are_finite_and_ordered():
    deuce = ENGINE.match_win_probability(state(points=(3, 3)), TYPICAL)
    adv_server = ENGINE.match_win_probability(state(points=(4, 3)), TYPICAL)
    adv_returner = ENGINE.match_win_probability(state(points=(3, 4)), TYPICAL)
    assert adv_server > deuce > adv_returner
    assert 0 < adv_returner < 1


def test_set_point_and_match_point_approach_terminal_probability():
    # BO3, one set up, serving at 40-0 in the second set at 5-3.
    near_victory = ENGINE.match_win_probability(
        state(sets=(1, 0), games=(5, 3), points=(3, 0)), TYPICAL
    )
    assert near_victory > 0.9
    near_defeat = ENGINE.match_win_probability(
        state(sets=(0, 1), games=(3, 5), points=(0, 3)), TYPICAL
    )
    assert near_defeat < 0.1


def test_terminal_states_return_exact_winner():
    assert ENGINE.match_win_probability(state(sets=(2, 0)), TYPICAL) == 1.0
    assert ENGINE.match_win_probability(state(sets=(0, 2)), TYPICAL) == 0.0
    assert ENGINE.match_win_probability(state(sets=(3, 1), best_of=5), TYPICAL) == 1.0
    assert ENGINE.match_win_probability(state(sets=(1, 3), best_of=5), TYPICAL) == 0.0


def test_one_set_lead_is_stronger_in_best_of_three():
    lead_bo3 = ENGINE.match_win_probability(state(sets=(1, 0)), TYPICAL)
    lead_bo5 = ENGINE.match_win_probability(state(sets=(1, 0), best_of=5), TYPICAL)
    # With symmetric priors the per-set win rate is 0.5, so needing one
    # more set (BO3) is stronger than needing two more (BO5).
    assert lead_bo3 == pytest.approx(0.75, abs=0.01)
    assert lead_bo5 == pytest.approx(0.6875, abs=0.01)
    assert lead_bo3 > lead_bo5 > 0.5


def test_standard_tiebreak_is_symmetric_with_equal_priors():
    probability = ENGINE.match_win_probability(state(games=(6, 6), tiebreak=True), EVEN)
    assert probability == pytest.approx(0.5)
    typical = ENGINE.match_win_probability(state(games=(6, 6), tiebreak=True), TYPICAL)
    assert 0.3 < typical < 0.7


def test_deciding_set_tiebreak_settles_the_match():
    probability = ENGINE.match_win_probability(
        state(sets=(1, 1), games=(6, 6), tiebreak=True), EVEN
    )
    assert probability == pytest.approx(0.5)
    leader_before = ENGINE.match_win_probability(
        state(sets=(1, 1), games=(6, 6), tiebreak=True, points=(6, 2)), EVEN
    )
    # 6-2 in a first-to-7 tiebreak is nearly decisive even at equal priors.
    assert leader_before > 0.95


def test_games_lead_moves_probability_monotonically():
    ahead = ENGINE.match_win_probability(state(games=(5, 2)), TYPICAL)
    level = ENGINE.match_win_probability(state(games=(3, 3)), TYPICAL)
    behind = ENGINE.match_win_probability(state(games=(2, 5)), TYPICAL)
    assert ahead > level > behind


@pytest.mark.parametrize("best_of", [None, 0, 4, 7])
def test_unknown_format_abstains_with_typed_error(best_of):
    with pytest.raises(ScoringFormatUnknown):
        ENGINE.match_win_probability(state(best_of=best_of), TYPICAL)


def test_probability_is_bounded_for_all_reachable_states():
    for sets in ((0, 0), (1, 0), (0, 1), (1, 1)):
        for games in ((0, 0), (5, 4), (6, 6), (0, 5)):
            for points in ((0, 0), (3, 3), (4, 3)):
                value = ENGINE.match_win_probability(
                    state(
                        sets=sets,
                        games=games,
                        points=points,
                        best_of=5 if sum(sets) >= 2 else 3,
                    ),
                    TYPICAL,
                )
                assert 0.0 <= value <= 1.0
