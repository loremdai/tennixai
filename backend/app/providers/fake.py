from collections.abc import Callable
from datetime import datetime, timezone

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
from app.errors import AppError
from app.identity import MemoryIdentityRepository


class FakeTennisProvider:
    """Deterministic in-process provider used by unit, API, and E2E tests."""

    def __init__(
        self,
        identities: MemoryIdentityRepository,
        now: Callable[[], datetime],
    ) -> None:
        self._identities = identities
        self._now = now

        sinner = Player(
            id=identities.get_or_create("player", "fake", "fake-sinner"),
            name="Jannik Sinner",
            country_code="ita",
            ranking=1,
        )
        alcaraz = Player(
            id=identities.get_or_create("player", "fake", "fake-alcaraz"),
            name="Carlos Alcaraz",
            country_code="esp",
            ranking=2,
        )
        djokovic = Player(
            id=identities.get_or_create("player", "fake", "fake-djokovic"),
            name="Novak Djokovic",
            country_code="srb",
            ranking=3,
        )
        ruud = Player(
            id=identities.get_or_create("player", "fake", "fake-ruud"),
            name="Casper Ruud",
            country_code="nor",
            ranking=4,
        )
        self._players = [sinner, alcaraz, djokovic, ruud]

        atp_finals = Tournament(
            id=identities.get_or_create("tournament", "fake", "fake-atp-finals"),
            name="ATP Finals",
            tour="atp",
        )

        self.sinner_alcaraz = Match(
            id=identities.get_or_create("match", "fake", "fake-upcoming"),
            status=MatchStatus.SCHEDULED,
            players=(sinner, alcaraz),
            tournament=atp_finals,
            scheduled_at=datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc),
            round="Semifinal",
            surface="hard",
            indoor=True,
            format="BO3",
            freshness=DataFreshness(provider="fake", observed_at=now()),
        )

        live_score = MatchScore(
            sets_won=(1, 1),
            sets=(
                SetScore(number=1, player1_games=6, player2_games=4),
                SetScore(number=2, player1_games=4, player2_games=6),
                SetScore(number=3, player1_games=4, player2_games=5),
            ),
            points=("30", "15"),
            is_tiebreak=False,
        )
        self.live_match = Match(
            id=identities.get_or_create("match", "fake", "fake-live"),
            status=MatchStatus.LIVE,
            players=(sinner, ruud),
            tournament=atp_finals,
            scheduled_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
            round="Semifinal",
            surface="hard",
            indoor=True,
            format="BO3",
            live_state=LiveMatchState(score=live_score, server_player_id=sinner.id),
            freshness=DataFreshness(
                provider="fake",
                source_updated_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                observed_at=now(),
            ),
        )

        self._matches: dict[str, Match] = {
            self.sinner_alcaraz.id: self.sinner_alcaraz,
            self.live_match.id: self.live_match,
        }

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        matches = [
            match for match in self._matches.values() if match.status is MatchStatus.LIVE
        ]
        return self._filter(matches, player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        matches = [
            match
            for match in self._matches.values()
            if match.status is MatchStatus.SCHEDULED
        ]
        return self._filter(matches, player_id)

    async def search_players(self, query: str) -> list[Player]:
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [player for player in self._players if normalized in player.name.casefold()]

    async def get_match(self, match_id: str) -> Match:
        match = self._matches.get(match_id)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_score(self, match_id: str) -> LiveMatchState:
        match = await self.get_match(match_id)
        if match.live_state is None:
            raise AppError("not_found", "Score not available", 404)
        return match.live_state

    @staticmethod
    def _filter(matches: list[Match], player_id: str | None) -> list[Match]:
        if player_id is None:
            return list(matches)
        return [
            match
            for match in matches
            if any(player.id == player_id for player in match.players)
        ]
