"""Shared P2 test fakes: multi-facet catalog provider and the fixed P2 clock.

Imported as `p2_fakes` (pytest inserts tests/ into sys.path for package-less
test directories); conftest only exposes fixtures.
"""

from datetime import datetime, timezone

from app.domain import (
    DataFreshness,
    HeadToHead,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.fake import FakeTennisProvider

# 2026-09-09T12:00Z == 2026-09-09 20:00 Asia/Macau; "yesterday" is 2026-09-08.
P2_NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


class CatalogFakeProvider(FakeTennisProvider):
    """Multi-facet fake dataset plus controllable history/H2H responses."""

    def __init__(self, now=None) -> None:
        super().__init__(
            identities=MemoryIdentityRepository(), now=now or (lambda: P2_NOW)
        )
        self.recent_calls = 0
        self.h2h_calls = 0
        self.recent_results: list[Match] = []
        self.recent_error: AppError | None = None
        self.h2h_meetings: list[Match] = []
        self.h2h_first_recent: list[Match] = []
        self.h2h_second_recent: list[Match] = []
        self.h2h_error: AppError | None = None

    async def _post_build(self) -> None:
        identities = self._identities
        now = self._now

        swiatek = Player(
            id=await identities.get_or_create("player", "fake", "fake-swiatek"),
            name="Iga Swiatek",
            country_code="pol",
            ranking=1,
        )
        sabalenka = Player(
            id=await identities.get_or_create("player", "fake", "fake-sabalenka"),
            name="Aryna Sabalenka",
            country_code="blr",
            ranking=2,
        )
        challenger_men = (
            next(p for p in self._players if p.name == "Novak Djokovic"),
            next(p for p in self._players if p.name == "Casper Ruud"),
        )
        itf_pair_a = Player(
            id=await identities.get_or_create("player", "fake", "fake-itf-pair-a"),
            name="Hontama/ Kubka",
        )
        itf_pair_b = Player(
            id=await identities.get_or_create("player", "fake", "fake-itf-pair-b"),
            name="Liu/ Sun",
        )
        other_a = Player(
            id=await identities.get_or_create("player", "fake", "fake-other-a"),
            name="Exhibition One",
        )
        other_b = Player(
            id=await identities.get_or_create("player", "fake", "fake-other-b"),
            name="Exhibition Two",
        )

        wta_finals = Tournament(
            id=await identities.get_or_create("tournament", "fake", "fake-wta-finals"),
            name="WTA Finals",
            tour="wta",
            circuit="wta",
            gender="women",
            discipline="singles",
        )
        challenger_tour = Tournament(
            id=await identities.get_or_create("tournament", "fake", "fake-challenger"),
            name="Seville Challenger",
            circuit="challenger",
            gender="men",
            discipline="singles",
        )
        itf_tour = Tournament(
            id=await identities.get_or_create("tournament", "fake", "fake-itf"),
            name="W15 Hurghada",
            circuit="itf",
            gender="women",
            discipline="doubles",
        )
        other_tour = Tournament(
            id=await identities.get_or_create("tournament", "fake", "fake-other"),
            name="Exhibition Night",
            circuit="other",
            gender="unknown",
            discipline="unknown",
        )

        def freshness() -> DataFreshness:
            return DataFreshness(provider="fake", observed_at=now())

        self.wta_live = Match(
            id=await identities.get_or_create("match", "fake", "fake-wta-live"),
            status=MatchStatus.LIVE,
            players=(swiatek, sabalenka),
            tournament=wta_finals,
            scheduled_at=datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc),
            freshness=freshness(),
        )
        self.wta_upcoming = Match(
            id=await identities.get_or_create("match", "fake", "fake-wta-upcoming"),
            status=MatchStatus.SCHEDULED,
            players=(sabalenka, swiatek),
            tournament=wta_finals,
            scheduled_at=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
            freshness=freshness(),
        )
        self.challenger_upcoming = Match(
            id=await identities.get_or_create("match", "fake", "fake-challenger-upcoming"),
            status=MatchStatus.SCHEDULED,
            players=challenger_men,
            tournament=challenger_tour,
            scheduled_at=datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
            freshness=freshness(),
        )
        self.itf_doubles_upcoming = Match(
            id=await identities.get_or_create("match", "fake", "fake-itf-doubles"),
            status=MatchStatus.SCHEDULED,
            players=(itf_pair_a, itf_pair_b),
            tournament=itf_tour,
            scheduled_at=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc),
            freshness=freshness(),
        )
        self.other_upcoming = Match(
            id=await identities.get_or_create("match", "fake", "fake-other-upcoming"),
            status=MatchStatus.SCHEDULED,
            players=(other_a, other_b),
            tournament=other_tour,
            scheduled_at=datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc),
            freshness=freshness(),
        )
        for match in (
            self.wta_live,
            self.wta_upcoming,
            self.challenger_upcoming,
            self.itf_doubles_upcoming,
            self.other_upcoming,
        ):
            self._matches[match.id] = match

    def finished_match(self, key: str, scheduled_at: datetime) -> Match:
        sinner = next(p for p in self._players if p.name == "Jannik Sinner")
        ruud = next(p for p in self._players if p.name == "Casper Ruud")
        return Match(
            id=f"mat_hist_{key}",
            status=MatchStatus.FINISHED,
            players=(sinner, ruud),
            tournament=self.sinner_alcaraz.tournament,
            scheduled_at=scheduled_at,
            winner_player_id=sinner.id,
            freshness=DataFreshness(provider="fake", observed_at=self._now()),
        )

    async def get_recent_results(self, player_id: str, *, limit: int) -> list[Match]:
        self.recent_calls += 1
        if self.recent_error is not None:
            raise self.recent_error
        await self.get_player(player_id)
        return list(self.recent_results)[: max(1, min(limit, 10))]

    async def get_head_to_head(
        self, first_player_id: str, second_player_id: str, *, limit: int
    ) -> HeadToHead:
        self.h2h_calls += 1
        if self.h2h_error is not None:
            raise self.h2h_error
        await self.get_player(first_player_id)
        await self.get_player(second_player_id)
        bounded = max(1, min(limit, 10))
        return HeadToHead(
            first_player_id=first_player_id,
            second_player_id=second_player_id,
            meetings=tuple(self.h2h_meetings[:bounded]),
            first_player_recent=tuple(self.h2h_first_recent[:bounded]),
            second_player_recent=tuple(self.h2h_second_recent[:bounded]),
            freshness=DataFreshness(provider="fake", observed_at=self._now()),
        )
