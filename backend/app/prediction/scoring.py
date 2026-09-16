"""Deterministic tennis scoring probability engine (T62).

Given the current sets/games/points, the server and the match format, the
engine computes the exact whole-match win probability under i.i.d. serve
point priors via memoized dynamic programming. Deuce and tiebreak-equality
tails use their closed-form two-point block solutions, so every result is
deterministic and bounded. Unknown formats abstain; nothing is guessed.
"""

from dataclasses import dataclass
from functools import lru_cache


class ScoringFormatUnknown(Exception):
    """Stable abstention: the match format is not a recognized best-of."""

    reason_code = "FORMAT_UNKNOWN"


@dataclass(frozen=True)
class ServePointPrior:
    p1_serve_win: float
    p2_serve_win: float

    def __post_init__(self) -> None:
        for value in (self.p1_serve_win, self.p2_serve_win):
            if not 0.0 <= value <= 1.0:
                raise ValueError("serve win probabilities must lie in [0, 1]")


@dataclass(frozen=True)
class TennisScoringState:
    """Point indices: 0..2 = 0/15/30, 3 = 40, 4 = advantage (diff rules)."""

    sets_won: tuple[int, int] = (0, 0)
    games_in_current_set: tuple[int, int] = (0, 0)
    points_in_current_game: tuple[int, int] = (0, 0)
    server: int = 0  # 0 = player1 serves, 1 = player2
    is_tiebreak: bool = False
    best_of: int | None = 3

    def __post_init__(self) -> None:
        if self.server not in (0, 1):
            raise ValueError("server must be 0 or 1")


def _server_game_probability(s: float) -> float:
    """Closed-form game win probability for the server at deuce tails."""
    return (s * s) / (s * s + (1.0 - s) * (1.0 - s)) if s not in (0.0, 1.0) else s


class ScoringProbabilityEngine:
    def match_win_probability(
        self, state: TennisScoringState, serve: ServePointPrior
    ) -> float:
        if state.best_of not in (3, 5):
            raise ScoringFormatUnknown(
                f"unrecognized match format best_of={state.best_of!r}"
            )
        sets_to_win = (state.best_of + 1) // 2
        s1, s2 = state.sets_won
        if s1 >= sets_to_win:
            return 1.0
        if s2 >= sets_to_win:
            return 0.0

        server_is_p1 = state.server == 0
        in_tiebreak = state.is_tiebreak or state.games_in_current_set == (6, 6)
        g1, g2 = state.games_in_current_set

        if in_tiebreak:
            p_now = self._tiebreak(
                state.points_in_current_game[0],
                state.points_in_current_game[1],
                server_is_p1,
                serve,
            )
            # Winning the tiebreak wins the set 7-6.
            after_win = self._contest(
                (s1 + 1, s2), (0, 0), not server_is_p1, serve, sets_to_win
            )
            after_lose = self._contest(
                (s1, s2 + 1), (0, 0), not server_is_p1, serve, sets_to_win
            )
        else:
            p_now = self._game(
                state.points_in_current_game[0],
                state.points_in_current_game[1],
                serve.p1_serve_win if server_is_p1 else serve.p2_serve_win,
                server_is_p1,
            )
            after_win = self._contest(
                (s1, s2), (g1 + 1, g2), not server_is_p1, serve, sets_to_win
            )
            after_lose = self._contest(
                (s1, s2), (g1, g2 + 1), not server_is_p1, serve, sets_to_win
            )
        return p_now * after_win + (1.0 - p_now) * after_lose

    # ------------------------------------------------------------------
    # Game level
    # ------------------------------------------------------------------

    def _game(
        self, p1_points: int, p2_points: int, s: float, server_is_p1: bool
    ) -> float:
        """Probability player 1 wins the current game. `s` is the server's
        point-win probability."""

        @lru_cache(maxsize=None)
        def win(pa: int, pb: int) -> float:
            # Terminal states are always from player 1's perspective.
            if pa >= 4 and pa - pb >= 2:
                return 1.0
            if pb >= 4 and pb - pa >= 2:
                return 0.0
            if pa >= 3 and pb >= 3:
                deuce = _server_game_probability(s)
                if pa == pb:
                    server_wins = deuce
                elif pa == pb + 1:
                    server_wins = s + (1.0 - s) * deuce
                else:  # pb == pa + 1
                    server_wins = s * deuce
                return server_wins if server_is_p1 else 1.0 - server_wins
            if server_is_p1:
                return s * win(pa + 1, pb) + (1.0 - s) * win(pa, pb + 1)
            return (1.0 - s) * win(pa + 1, pb) + s * win(pa, pb + 1)

        try:
            return win(p1_points, p2_points)
        finally:
            win.cache_clear()

    # ------------------------------------------------------------------
    # Tiebreak level
    # ------------------------------------------------------------------

    def _tiebreak(
        self, t1: int, t2: int, first_server_is_p1: bool, serve: ServePointPrior
    ) -> float:
        """Probability player 1 wins the tiebreak (first to 7, win by 2).

        Serve order: point 1 goes to the first server, then servers alternate
        every two points. Equality tails at 6-6+ use the exact two-point
        block closed form.
        """
        s_when_p1_serves = serve.p1_serve_win
        s_when_p2_serves = 1.0 - serve.p2_serve_win

        def point_server_is_p1(point_number: int) -> bool:
            if point_number == 1:
                return first_server_is_p1
            other = not first_server_is_p1
            return other if ((point_number - 2) // 2) % 2 == 0 else not other

        @lru_cache(maxsize=None)
        def win(a: int, b: int) -> float:
            if a >= 7 and a - b >= 2:
                return 1.0
            if b >= 7 and b - a >= 2:
                return 0.0
            if a == b and a >= 6:
                # Two-point blocks: block servers are (X, Y) then (Y, X);
                # the win/lose products are identical, giving an exact
                # closed form for the win-by-2 tail.
                s_a = (
                    s_when_p1_serves
                    if point_server_is_p1(2 * a + 1)
                    else s_when_p2_serves
                )
                s_b = (
                    s_when_p1_serves
                    if point_server_is_p1(2 * a + 2)
                    else s_when_p2_serves
                )
                w = s_a * s_b
                lose = (1.0 - s_a) * (1.0 - s_b)
                if w + lose == 0:
                    return 0.5
                return w / (w + lose)
            n = a + b + 1
            s = s_when_p1_serves if point_server_is_p1(n) else s_when_p2_serves
            return s * win(a + 1, b) + (1.0 - s) * win(a, b + 1)

        try:
            return win(t1, t2)
        finally:
            win.cache_clear()

    # ------------------------------------------------------------------
    # Set / match level
    # ------------------------------------------------------------------

    def _contest(
        self,
        sets: tuple[int, int],
        games: tuple[int, int],
        server_is_p1: bool,
        serve: ServePointPrior,
        sets_to_win: int,
    ) -> float:
        """Probability player 1 wins the match starting at the beginning of
        a game inside the current set."""

        @lru_cache(maxsize=None)
        def contest(s1: int, s2: int, g1: int, g2: int, srv: bool) -> float:
            if s1 >= sets_to_win:
                return 1.0
            if s2 >= sets_to_win:
                return 0.0
            if g1 >= 6 and g1 - g2 >= 2:
                return contest(s1 + 1, s2, 0, 0, not srv)
            if g2 >= 6 and g2 - g1 >= 2:
                return contest(s1, s2 + 1, 0, 0, not srv)
            if g1 == 6 and g2 == 6:
                p_tb = self._tiebreak(0, 0, srv, serve)
                return p_tb * contest(s1 + 1, s2, 0, 0, not srv) + (
                    1.0 - p_tb
                ) * contest(s1, s2 + 1, 0, 0, not srv)
            s = serve.p1_serve_win if srv else serve.p2_serve_win
            p_game = self._game(0, 0, s, srv)
            return p_game * contest(s1, s2, g1 + 1, g2, not srv) + (
                1.0 - p_game
            ) * contest(s1, s2, g1, g2 + 1, not srv)

        try:
            return contest(sets[0], sets[1], games[0], games[1], server_is_p1)
        finally:
            contest.cache_clear()
