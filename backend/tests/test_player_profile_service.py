"""Player profile/results service composition tests (deterministic fakes)."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

from app.cache import AsyncTTLCache
from app.domain import (
    CircuitTier,
    DataFreshness,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.players.models import (
    PlayerProfileData,
    PlayerSeasonRecord,
    RankingEntry,
    RankingMovement,
    ResultOutcome,
    SurfaceRecord,
    Tour,
)
from app.players.repository import MemoryPlayerDirectoryRepository
from app.service import TennisService

UTC = timezone.utc
NOW_UTC = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

SINNER = Player(id="ply_s", name="Jannik Sinner", ranking=1)
ZHENG = Player(id="ply_z", name="Qinwen Zheng", ranking=5)
OPPONENT = Player(id="ply_o", name="Opponent One", ranking=40)


def _seasons() -> tuple[PlayerSeasonRecord, ...]:
    return tuple(
        PlayerSeasonRecord(
            season=2026 - index,
            matches_won=30 - index * 3,
            matches_lost=10 + index,
            titles=max(0, 2 - index),
            hard=SurfaceRecord(won=20 - index * 2, lost=5 + index) if index < 4 else None,
            clay=SurfaceRecord(won=8 - index, lost=3 + index) if index < 4 else None,
            grass=SurfaceRecord(won=2, lost=2) if index < 3 else None,
        )
        for index in range(5)
    )


def _finished_match(index: int, season: int, circuit: str, zheng_wins: bool) -> Match:
    return Match(
        id=f"mat_fin_{season}_{index}",
        status=MatchStatus.FINISHED,
        players=(ZHENG, OPPONENT),
        tournament=Tournament(id=f"trn_{circuit}_{index}", name=f"Event {index}", tour="wta", circuit=CircuitTier(circuit)),
        scheduled_at=datetime(season, 1, 5, 10, 0, tzinfo=UTC) + timedelta(days=index * 3),
        winner_player_id=ZHENG.id if zheng_wins else OPPONENT.id,
        freshness=DataFreshness(provider="fake", observed_at=NOW_UTC),
    )


class ProfileProvider:
    """Deterministic profile/results provider with call counting."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.live: list[Match] = []
        self.upcoming: list[Match] = []
        self._finished: tuple[Match, ...] = (
            tuple(
                _finished_match(index, 2026, circuit, index % 3 != 2)
                for index, circuit in enumerate(
                    ["wta"] * 18 + ["challenger"] * 3 + ["itf"] * 2
                )
            )
            + tuple(_finished_match(index, 2025, "wta", index % 2 == 0) for index in range(5))
        )

    async def get_player_profile(self, player_id: str) -> PlayerProfileData:
        self.calls["profile"] += 1
        player = {SINNER.id: SINNER, ZHENG.id: ZHENG}.get(player_id)
        if player is None:
            raise AppError("not_found", "Player not found", 404)
        return PlayerProfileData(
            player=player,
            birth_date=date(2000, 1, 1),
            image_url=None,
            seasons=_seasons(),
        )

    async def get_player_results_for_period(
        self, player_id: str, *, start: date, end: date
    ) -> tuple[Match, ...]:
        self.calls["results"] += 1
        return tuple(
            match
            for match in self._finished
            if start <= match.scheduled_at.date() <= end
        )

    # minimal list surface used by current_match composition
    async def get_live_matches(self, *, player_id: str | None = None):
        self.calls["live"] += 1
        return [m for m in self.live if player_id is None or any(p.id == player_id for p in m.players)]

    async def get_fixtures(self, *, player_id: str | None = None):
        self.calls["fixtures"] += 1
        return [m for m in self.upcoming if player_id is None or any(p.id == player_id for p in m.players)]


def build_service(provider: ProfileProvider, directory: MemoryPlayerDirectoryRepository):
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=64)
    return TennisService(
        provider,
        cache,
        now=lambda: NOW_UTC,
        timezone="Asia/Macau",
        directory=directory,
    )


@pytest.fixture()
async def seeded_directory() -> MemoryPlayerDirectoryRepository:
    directory = MemoryPlayerDirectoryRepository()
    await directory.save_ranking_snapshot(
        (
            RankingEntry(
                player=SINNER, tour=Tour.ATP, rank=1, points=100,
                movement=RankingMovement.SAME, ranking_date=NOW_UTC.date(), fetched_at=NOW_UTC,
            ),
            RankingEntry(
                player=ZHENG, tour=Tour.WTA, rank=5, points=90,
                movement=RankingMovement.UP, ranking_date=NOW_UTC.date(), fetched_at=NOW_UTC,
            ),
        )
    )
    return directory


@pytest.mark.asyncio
async def test_rankings_page_reads_directory(seeded_directory) -> None:
    service = build_service(ProfileProvider(), seeded_directory)

    page = await service.get_rankings_page(Tour.ATP, page=1, page_size=50, country_code=None)
    assert page.total == 1
    assert page.entries[0].player.id == SINNER.id
    assert page.page_size == 50

    wta = await service.get_rankings_page(Tour.WTA, page=1, page_size=50, country_code=None)
    assert wta.entries[0].player.id == ZHENG.id


@pytest.mark.asyncio
async def test_profile_view_selects_season_and_current_match_none(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)
    assert view.profile.player.id == ZHENG.id
    assert view.selected_season == 2026
    assert view.season_record is not None
    assert view.season_record.matches_won == 30
    assert view.season_record.grass is not None
    assert view.current_match is None

    # profile fetch is cached for one hour
    await service.get_player_profile_view(ZHENG.id, season=2025)
    assert provider.calls["profile"] == 1


@pytest.mark.asyncio
async def test_profile_view_prefers_live_over_next(seeded_directory) -> None:
    provider = ProfileProvider()
    live = Match(
        id="mat_live_z", status=MatchStatus.LIVE, players=(ZHENG, OPPONENT),
        tournament=Tournament(id="trn_l", name="Live Event", tour="wta"),
        scheduled_at=NOW_UTC - timedelta(hours=1),
        freshness=DataFreshness(provider="fake", observed_at=NOW_UTC),
    )
    upcoming = Match(
        id="mat_next_z", status=MatchStatus.SCHEDULED, players=(ZHENG, OPPONENT),
        tournament=Tournament(id="trn_n", name="Next Event", tour="wta"),
        scheduled_at=NOW_UTC + timedelta(hours=5),
        freshness=DataFreshness(provider="fake", observed_at=NOW_UTC),
    )
    provider.live = [live]
    provider.upcoming = [upcoming]
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)
    assert view.current_match is not None
    assert view.current_match.id == "mat_live_z"


@pytest.mark.asyncio
async def test_profile_unknown_player_is_not_found(seeded_directory) -> None:
    service = build_service(ProfileProvider(), seeded_directory)
    with pytest.raises(AppError) as failure:
        await service.get_player_profile_view("ply_missing", season=2026)
    assert failure.value.code == "not_found"


@pytest.mark.asyncio
async def test_result_page_paginates_and_filters(seeded_directory) -> None:
    provider = ProfileProvider()
    service = build_service(provider, seeded_directory)

    page1 = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=1
    )
    assert page1.total == 23
    assert len(page1.matches) == 20
    page2 = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=2
    )
    assert len(page2.matches) == 3

    itf = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(CircuitTier.ITF,), outcome=ResultOutcome.ALL, page=1
    )
    assert itf.total == 2
    assert all(match.tournament.circuit is CircuitTier.ITF for match in itf.matches)

    lost = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.LOST, page=1
    )
    assert lost.total == sum(1 for index in range(18 + 3 + 2) if index % 3 == 2)
    assert all(match.winner_player_id != ZHENG.id for match in lost.matches)

    # one-season raw fetch is cached
    before = provider.calls["results"]
    await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=1
    )
    assert provider.calls["results"] == before


@pytest.mark.asyncio
async def test_result_page_rejects_out_of_range_season(seeded_directory) -> None:
    service = build_service(ProfileProvider(), seeded_directory)
    with pytest.raises(AppError) as failure:
        await service.get_player_result_page(
            ZHENG.id, season=2021, tiers=(), outcome=ResultOutcome.ALL, page=1
        )
    assert failure.value.code == "invalid_request"


class LongHistoryProvider(ProfileProvider):
    """Supplier payload carrying seasons outside the product window."""

    async def get_player_profile(self, player_id: str) -> PlayerProfileData:
        base = await super().get_player_profile(player_id)
        extra = tuple(
            PlayerSeasonRecord(season=2021 - index, matches_won=1, matches_lost=1, titles=0)
            for index in range(3)
        )
        return base.model_copy(update={"seasons": base.seasons + extra})


@pytest.mark.asyncio
async def test_profile_view_windows_supplier_history_to_five_seasons(
    seeded_directory,
) -> None:
    service = build_service(LongHistoryProvider(), seeded_directory)

    view = await service.get_player_profile_view(SINNER.id)
    assert [record.season for record in view.profile.seasons] == [
        2026,
        2025,
        2024,
        2023,
        2022,
    ]
