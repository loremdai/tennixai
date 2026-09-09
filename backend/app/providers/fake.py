import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from app.domain import (
    CapabilityStatus,
    DataFreshness,
    DataQuality,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatus,
    Player,
    SetScore,
    Tournament,
)
from app.errors import AppError
from app.identity import IdentityRepository

SNAPSHOT_GAP_CAPABILITIES = ("point_by_point", "statistics", "momentum")


class FakeTennisProvider:
    """Deterministic in-process provider used by unit, API, and E2E tests.

    Construction is synchronous; canonical state is built on the first awaited
    call (or explicitly via `build()` / `create()`) because identity access is
    async in P2. Subclasses extend the dataset by overriding `_post_build`.
    """

    def __init__(
        self,
        identities: IdentityRepository,
        now: Callable[[], datetime],
    ) -> None:
        self._identities = identities
        self._now = now
        self._build_lock = asyncio.Lock()
        self._built = False
        self._players: list[Player] = []
        self._matches: dict[str, Match] = {}
        self.sinner_alcaraz: Match | None = None
        self.live_match: Match | None = None

    @classmethod
    async def create(
        cls,
        identities: IdentityRepository,
        now: Callable[[], datetime],
    ) -> "FakeTennisProvider":
        provider = cls(identities=identities, now=now)
        await provider.build()
        return provider

    async def build(self) -> None:
        async with self._build_lock:
            if self._built:
                return
            await self._build_state()
            await self._post_build()
            self._built = True

    async def _post_build(self) -> None:
        """Hook for subclasses; runs once at the end of `build()`."""

    async def _build_state(self) -> None:
        identities = self._identities
        now = self._now

        sinner = Player(
            id=await identities.get_or_create("player", "fake", "fake-sinner"),
            name="Jannik Sinner",
            country_code="ita",
            ranking=1,
        )
        alcaraz = Player(
            id=await identities.get_or_create("player", "fake", "fake-alcaraz"),
            name="Carlos Alcaraz",
            country_code="esp",
            ranking=2,
        )
        djokovic = Player(
            id=await identities.get_or_create("player", "fake", "fake-djokovic"),
            name="Novak Djokovic",
            country_code="srb",
            ranking=3,
        )
        ruud = Player(
            id=await identities.get_or_create("player", "fake", "fake-ruud"),
            name="Casper Ruud",
            country_code="nor",
            ranking=4,
        )
        self._players = [sinner, alcaraz, djokovic, ruud]

        atp_finals = Tournament(
            id=await identities.get_or_create("tournament", "fake", "fake-atp-finals"),
            name="ATP Finals",
            tour="atp",
        )

        self.sinner_alcaraz = Match(
            id=await identities.get_or_create("match", "fake", "fake-upcoming"),
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
            id=await identities.get_or_create("match", "fake", "fake-live"),
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

        self._matches = {
            self.sinner_alcaraz.id: self.sinner_alcaraz,
            self.live_match.id: self.live_match,
        }

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        await self.build()
        matches = [
            match for match in self._matches.values() if match.status is MatchStatus.LIVE
        ]
        return self._filter(matches, player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        await self.build()
        matches = [
            match
            for match in self._matches.values()
            if match.status is MatchStatus.SCHEDULED
        ]
        return self._filter(matches, player_id)

    async def search_players(self, query: str) -> list[Player]:
        await self.build()
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [player for player in self._players if normalized in player.name.casefold()]

    async def get_player(self, player_id: str) -> Player:
        await self.build()
        for player in self._players:
            if player.id == player_id:
                return player
        raise AppError("not_found", "Player not found", 404)

    async def get_match(self, match_id: str) -> Match:
        await self.build()
        match = self._matches.get(match_id)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        match = await self.get_match(match_id)
        live_state = match.live_state
        observed_at = match.freshness.observed_at
        return MatchSnapshot(
            match=match,
            quality=tuple(
                DataQuality(
                    capability=capability,
                    status=CapabilityStatus.UNAVAILABLE,
                    provider="fake",
                    reason="not_reported",
                    observed_at=observed_at,
                )
                for capability in SNAPSHOT_GAP_CAPABILITIES
            ),
            state_version=live_state.state_version if live_state is not None else 0,
            as_of=observed_at,
        )

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        await self.get_player(player_id)
        # The deterministic fake dataset contains no finished matches; an
        # honest empty result beats fabricated history.
        return []

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        await self.get_player(first_player_id)
        await self.get_player(second_player_id)
        return HeadToHead(
            first_player_id=first_player_id,
            second_player_id=second_player_id,
            freshness=DataFreshness(provider="fake", observed_at=self._now()),
        )

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
