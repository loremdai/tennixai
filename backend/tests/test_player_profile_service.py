"""Player profile/results service composition tests (deterministic fakes)."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

from app.cache import AsyncTTLCache
from app.domain import (
    CapabilityStatus,
    CircuitTier,
    DataFreshness,
    Discipline,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.errors import AppError
from app.players.models import (
    LocalizedNameUpdate,
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
        tournament=Tournament(
            id=f"trn_{circuit}_{index}",
            name=f"Event {index}",
            tour="wta",
            circuit=CircuitTier(circuit),
            discipline=Discipline.SINGLES,
        ),
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
        self.reported_profile_rank: int | None = None
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
        if self.reported_profile_rank is not None and player_id == ZHENG.id:
            player = player.model_copy(update={"ranking": self.reported_profile_rank})
        return PlayerProfileData(
            player=player,
            birth_date=date(2000, 1, 1),
            image_url=None,
            seasons=_seasons(),
        )

    async def get_player(self, player_id: str) -> Player:
        self.calls["player"] += 1
        player = {SINNER.id: SINNER, ZHENG.id: ZHENG, OPPONENT.id: OPPONENT}.get(
            player_id
        )
        if player is None:
            raise AppError("not_found", "Player not found", 404)
        if self.reported_profile_rank is not None and player_id == ZHENG.id:
            player = player.model_copy(update={"ranking": self.reported_profile_rank})
        return player

    async def get_match(self, match_id: str) -> Match:
        match = _finished_match(0, 2026, "wta", True)
        match = match.model_copy(
            update={
                "id": match_id,
                "players": (
                    ZHENG.model_copy(update={"ranking": 72}),
                    OPPONENT,
                ),
            }
        )
        return match

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
        timezone="Asia/Shanghai",
        directory=directory,
    )


@pytest.fixture()
async def seeded_directory() -> MemoryPlayerDirectoryRepository:
    directory = MemoryPlayerDirectoryRepository()
    previous = NOW_UTC - timedelta(days=7)
    await directory.save_ranking_snapshot(
        (
            RankingEntry(
                player=SINNER, tour=Tour.ATP, rank=2, points=100,
                movement=RankingMovement.UNKNOWN, ranking_date=previous.date(), fetched_at=previous,
            ),
            RankingEntry(
                player=ZHENG, tour=Tour.WTA, rank=6, points=90,
                movement=RankingMovement.UNKNOWN, ranking_date=previous.date(), fetched_at=previous,
            ),
        )
    )
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
async def test_empty_country_filter_keeps_the_rankings_snapshot_time(
    seeded_directory,
) -> None:
    service = TennisService(
        ProfileProvider(),
        AsyncTTLCache(max_entries=64),
        now=lambda: NOW_UTC + timedelta(days=1),
        timezone="Asia/Shanghai",
        directory=seeded_directory,
    )

    page = await service.get_rankings_page(
        Tour.ATP, page=1, page_size=50, country_code="chn"
    )

    assert page.total == 0
    assert page.as_of == NOW_UTC


@pytest.mark.asyncio
async def test_rankings_page_has_no_as_of_when_no_snapshot_exists() -> None:
    service = build_service(ProfileProvider(), MemoryPlayerDirectoryRepository())

    page = await service.get_rankings_page(
        Tour.ATP, page=1, page_size=50, country_code=None
    )

    assert page.availability is CapabilityStatus.UNAVAILABLE
    assert page.as_of is None


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
async def test_profile_default_season_uses_beijing_calendar_year() -> None:
    now = datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
    service = build_service_with_now(ProfileProvider(), now)

    view = await service.get_player_profile_view(ZHENG.id)

    assert view.selected_season == 2027


@pytest.mark.asyncio
async def test_profile_current_rank_comes_from_latest_directory_snapshot(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    provider.reported_profile_rank = 72
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)

    assert view.profile.player.ranking == 5
    assert view.ranking is not None
    assert view.ranking.rank == 5
    assert view.ranking.points == 90
    assert view.ranking.movement is RankingMovement.UP


@pytest.mark.asyncio
async def test_match_current_rank_comes_from_directory_not_provider_profile(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    provider.reported_profile_rank = 72
    service = build_service(provider, seeded_directory)

    match = await service.get_match("mat_rank_source")

    assert match.players[0].ranking == 5
    assert match.players[1].ranking is None


@pytest.mark.asyncio
async def test_profile_view_prefers_live_over_next(seeded_directory) -> None:
    provider = ProfileProvider()
    live = Match(
        id="mat_live_z", status=MatchStatus.LIVE, players=(ZHENG, OPPONENT),
        tournament=Tournament(
            id="trn_l", name="Live Event", tour="wta", discipline=Discipline.SINGLES
        ),
        scheduled_at=NOW_UTC - timedelta(hours=1),
        freshness=DataFreshness(provider="fake", observed_at=NOW_UTC),
    )
    upcoming = Match(
        id="mat_next_z", status=MatchStatus.SCHEDULED, players=(ZHENG, OPPONENT),
        tournament=Tournament(
            id="trn_n", name="Next Event", tour="wta", discipline=Discipline.SINGLES
        ),
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
async def test_profile_view_selects_earliest_upcoming_match_not_provider_order(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    later = _finished_match(1, 2026, "wta", True).model_copy(
        update={
            "id": "mat_later",
            "status": MatchStatus.SCHEDULED,
            "scheduled_at": NOW_UTC + timedelta(days=2),
            "winner_player_id": None,
        }
    )
    earlier = _finished_match(2, 2026, "wta", True).model_copy(
        update={
            "id": "mat_earlier",
            "status": MatchStatus.SCHEDULED,
            "scheduled_at": NOW_UTC + timedelta(days=1),
            "winner_player_id": None,
        }
    )
    provider.upcoming = [later, earlier]
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)

    assert view.current_match is not None
    assert view.current_match.id == earlier.id


@pytest.mark.asyncio
async def test_profile_current_match_excludes_doubles(seeded_directory) -> None:
    provider = ProfileProvider()
    doubles_live = _finished_match(1, 2026, "wta", True).model_copy(
        update={
            "id": "mat_doubles_live",
            "status": MatchStatus.LIVE,
            "tournament": _finished_match(1, 2026, "wta", True).tournament.model_copy(
                update={"discipline": Discipline.DOUBLES}
            ),
            "scheduled_at": NOW_UTC - timedelta(hours=1),
            "winner_player_id": None,
        }
    )
    next_singles = _finished_match(2, 2026, "wta", True).model_copy(
        update={
            "id": "mat_singles_next",
            "status": MatchStatus.SCHEDULED,
            "scheduled_at": NOW_UTC + timedelta(days=1),
            "winner_player_id": None,
        }
    )
    provider.live = [doubles_live]
    provider.upcoming = [next_singles]
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)

    assert view.current_match is not None
    assert view.current_match.id == next_singles.id


@pytest.mark.asyncio
async def test_profile_current_match_uses_canonical_opponent_identity(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    provider.upcoming = [
        _finished_match(100, 2026, "wta", True).model_copy(
            update={
                "status": MatchStatus.SCHEDULED,
                "players": (ZHENG, Player(id=OPPONENT.id, name="O. One")),
                "winner_player_id": None,
                "scheduled_at": NOW_UTC + timedelta(hours=1),
            }
        )
    ]
    await seeded_directory.save_ranking_snapshot(
        (
            RankingEntry(
                player=Player(
                    id=OPPONENT.id,
                    name="Opponent Full Name",
                    country_code="gbr",
                ),
                tour=Tour.ATP,
                rank=40,
                points=500,
                movement=RankingMovement.UNKNOWN,
                ranking_date=(NOW_UTC + timedelta(days=1)).date(),
                fetched_at=NOW_UTC + timedelta(days=1),
            ),
        )
    )
    await seeded_directory.save_localized_names(
        (LocalizedNameUpdate(player_id=OPPONENT.id, localized_name="对手中文名"),)
    )
    service = build_service(provider, seeded_directory)

    view = await service.get_player_profile_view(ZHENG.id, season=2026)

    assert view.current_match is not None
    opponent = view.current_match.players[1]
    assert opponent.name == "Opponent Full Name"
    assert opponent.localized_name == "对手中文名"
    assert opponent.country_code == "gbr"


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
async def test_result_page_enriches_provider_abbreviations_from_player_directory(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    abbreviated_opponent = Player(id=OPPONENT.id, name="O. One")
    provider._finished = (
        provider._finished[0].model_copy(
            update={
                "players": (ZHENG, abbreviated_opponent),
                "scheduled_at": NOW_UTC - timedelta(minutes=5),
            }
        ),
        *provider._finished[1:],
    )
    await seeded_directory.save_ranking_snapshot(
        (
            RankingEntry(
                player=Player(
                    id=OPPONENT.id,
                    name="Opponent Full Name",
                    country_code="gbr",
                ),
                tour=Tour.ATP,
                rank=40,
                points=500,
                movement=RankingMovement.UNKNOWN,
                ranking_date=(NOW_UTC + timedelta(days=1)).date(),
                fetched_at=NOW_UTC + timedelta(days=1),
            ),
        )
    )
    await seeded_directory.save_localized_names(
        (LocalizedNameUpdate(player_id=OPPONENT.id, localized_name="对手中文名"),)
    )
    service = build_service(provider, seeded_directory)

    results = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=1
    )

    opponent = results.matches[0].players[1]
    assert opponent.id == OPPONENT.id
    assert opponent.name == "Opponent Full Name"
    assert opponent.localized_name == "对手中文名"
    assert opponent.country_code == "gbr"


@pytest.mark.asyncio
async def test_result_page_excludes_doubles_from_singles_history(seeded_directory) -> None:
    provider = ProfileProvider()
    doubles = _finished_match(10, 2026, "wta", True).model_copy(
        update={
            "id": "mat_doubles_history",
            "tournament": _finished_match(10, 2026, "wta", True).tournament.model_copy(
                update={"discipline": Discipline.DOUBLES}
            ),
        }
    )
    provider._finished += (doubles,)
    service = build_service(provider, seeded_directory)

    result = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=1
    )

    assert result.total == 23
    assert all(match.tournament.discipline is Discipline.SINGLES for match in result.matches)
    assert "mat_doubles_history" not in {match.id for match in result.matches}


@pytest.mark.asyncio
async def test_result_page_does_not_call_unknown_winner_a_loss(seeded_directory) -> None:
    provider = ProfileProvider()
    unknown_winner = _finished_match(30, 2026, "wta", True).model_copy(
        update={"id": "mat_unknown_winner", "winner_player_id": None}
    )
    provider._finished += (unknown_winner,)
    service = build_service(provider, seeded_directory)

    losses = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.LOST, page=1
    )

    assert "mat_unknown_winner" not in {match.id for match in losses.matches}


@pytest.mark.asyncio
async def test_successful_empty_season_results_are_available_not_unavailable(
    seeded_directory,
) -> None:
    service = build_service(ProfileProvider(), seeded_directory)

    result = await service.get_player_result_page(
        ZHENG.id, season=2024, tiers=(), outcome=ResultOutcome.ALL, page=1
    )

    assert result.availability is CapabilityStatus.AVAILABLE
    assert result.total == 0
    assert result.matches == ()


@pytest.mark.asyncio
async def test_result_page_marks_undated_matches_partial() -> None:
    undated = _finished_match(0, 2026, "wta", True).model_copy(
        update={"id": "mat_undated", "scheduled_at": None}
    )
    provider = SeasonResultsProvider({2026: (undated,)})
    service = TennisService(
        provider,
        AsyncTTLCache(max_entries=64),
        now=lambda: NOW_UTC,
        timezone="Asia/Shanghai",
    )

    result = await service.get_player_result_page(
        ZHENG.id, season=2026, tiers=(), outcome=ResultOutcome.ALL, page=1
    )

    assert result.availability is CapabilityStatus.PARTIAL
    assert [match.id for match in result.matches] == ["mat_undated"]


@pytest.mark.asyncio
async def test_result_page_rejects_out_of_range_season(seeded_directory) -> None:
    service = build_service(ProfileProvider(), seeded_directory)
    with pytest.raises(AppError) as failure:
        await service.get_player_result_page(
            ZHENG.id, season=2021, tiers=(), outcome=ResultOutcome.ALL, page=1
        )
    assert failure.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_result_page_accepts_current_beijing_season_at_utc_year_boundary() -> None:
    now = datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
    service = build_service_with_now(ProfileProvider(), now)

    result = await service.get_player_result_page(
        ZHENG.id, season=2027, tiers=(), outcome=ResultOutcome.ALL, page=1
    )

    assert result.season == 2027
    assert result.total == 0


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


# ------------------------------------------------- T54 latest-results semantics


def _result(
    match_id: str,
    scheduled_at: datetime | None,
    status: MatchStatus = MatchStatus.FINISHED,
) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=(ZHENG, OPPONENT),
        tournament=Tournament(
            id="trn_hist",
            name="History Event",
            tour="wta",
            discipline=Discipline.SINGLES,
        ),
        scheduled_at=scheduled_at,
        winner_player_id=ZHENG.id,
        freshness=DataFreshness(provider="fake", observed_at=NOW_UTC),
    )


class SeasonResultsProvider(ProfileProvider):
    """Per-season finished results with explicit season-load counting."""

    def __init__(self, by_season: dict[int, tuple[Match, ...]] | None = None) -> None:
        super().__init__()
        self.by_season = by_season or {}
        self.season_loads: list[int] = []

    async def get_player_results_for_period(
        self, player_id: str, *, start: date, end: date
    ) -> tuple[Match, ...]:
        self.calls["results"] += 1
        self.season_loads.append(start.year)
        return tuple(self.by_season.get(start.year, ()))


def build_service_with_now(provider: ProfileProvider, now: datetime):
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=64)
    return TennisService(
        provider,
        cache,
        now=lambda: now,
        timezone="Asia/Shanghai",
    )


@pytest.mark.asyncio
async def test_latest_results_return_match_older_than_thirty_days() -> None:
    old = _result("mat_old", datetime(2026, 6, 1, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider({2026: (old,)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=1)

    assert [match.id for match in results] == ["mat_old"]
    assert provider.season_loads == [2026]


@pytest.mark.asyncio
async def test_latest_results_limit_one_queries_only_newest_season() -> None:
    newest = _result("mat_new", datetime(2026, 8, 20, 10, 0, tzinfo=UTC))
    older = _result("mat_older", datetime(2026, 7, 1, 10, 0, tzinfo=UTC))
    prior = _result("mat_prior", datetime(2025, 12, 1, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider({2026: (older, newest), 2025: (prior,)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=1)

    assert [match.id for match in results] == ["mat_new"]
    assert provider.season_loads == [2026]


@pytest.mark.asyncio
async def test_latest_results_span_year_boundary_and_stop_early() -> None:
    jan_10 = _result("mat_jan10", datetime(2026, 1, 10, 10, 0, tzinfo=UTC))
    jan_5 = _result("mat_jan5", datetime(2026, 1, 5, 10, 0, tzinfo=UTC))
    dec_28 = _result("mat_dec28", datetime(2025, 12, 28, 10, 0, tzinfo=UTC))
    dec_20 = _result("mat_dec20", datetime(2025, 12, 20, 10, 0, tzinfo=UTC))
    dec_10 = _result("mat_dec10", datetime(2025, 12, 10, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider(
        {2026: (jan_5, jan_10), 2025: (dec_10, dec_20, dec_28)}
    )
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=4)

    assert [match.id for match in results] == [
        "mat_jan10",
        "mat_jan5",
        "mat_dec28",
        "mat_dec20",
    ]
    assert provider.season_loads == [2026, 2025]


@pytest.mark.asyncio
async def test_latest_results_deduplicate_by_canonical_id() -> None:
    shared = _result("mat_shared", datetime(2026, 6, 1, 10, 0, tzinfo=UTC))
    prior = _result("mat_prior", datetime(2025, 5, 1, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider(
        {2026: (shared,), 2025: (shared.model_copy(), prior)}
    )
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=2)

    assert [match.id for match in results] == ["mat_shared", "mat_prior"]
    assert provider.season_loads == [2026, 2025]


@pytest.mark.asyncio
async def test_latest_results_exclude_non_finished_and_undated() -> None:
    finished = _result("mat_fin", datetime(2026, 3, 1, 10, 0, tzinfo=UTC))
    noise = (
        _result("mat_live", datetime(2026, 8, 1, 10, 0, tzinfo=UTC), MatchStatus.LIVE),
        _result("mat_sch", datetime(2026, 9, 20, 10, 0, tzinfo=UTC), MatchStatus.SCHEDULED),
        _result("mat_can", datetime(2026, 7, 1, 10, 0, tzinfo=UTC), MatchStatus.CANCELLED),
        _result("mat_post", datetime(2026, 7, 2, 10, 0, tzinfo=UTC), MatchStatus.POSTPONED),
        _result("mat_unk", datetime(2026, 7, 3, 10, 0, tzinfo=UTC), MatchStatus.UNKNOWN),
        _result("mat_nodate", None),
    )
    provider = SeasonResultsProvider({2026: (*noise, finished)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=1)

    assert [match.id for match in results] == ["mat_fin"]
    assert provider.season_loads == [2026]


@pytest.mark.asyncio
async def test_latest_results_tie_break_by_internal_id() -> None:
    same_time = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    match_a = _result("mat_a", same_time)
    match_b = _result("mat_b", same_time)
    provider = SeasonResultsProvider({2026: (match_a, match_b)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=2)

    assert [match.id for match in results] == ["mat_b", "mat_a"]


@pytest.mark.asyncio
async def test_latest_results_exhaust_exactly_five_seasons_with_empty_success() -> None:
    provider = SeasonResultsProvider({})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_latest_player_results(ZHENG.id, limit=10)

    assert results == ()
    assert provider.season_loads == [2026, 2025, 2024, 2023, 2022]


@pytest.mark.asyncio
async def test_latest_results_invalid_limit_fails_before_provider_access() -> None:
    provider = SeasonResultsProvider({})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    for invalid_limit in (0, 11):
        with pytest.raises(AppError) as failure:
            await service.get_latest_player_results(ZHENG.id, limit=invalid_limit)
        assert failure.value.code == "invalid_request"
    assert provider.season_loads == []


@pytest.mark.asyncio
async def test_latest_results_use_beijing_calendar_year() -> None:
    # 2026-12-31T18:00Z is already 2027-01-01 02:00 in Asia/Shanghai.
    new_year_edge = datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
    provider = SeasonResultsProvider({})
    service = build_service_with_now(provider, new_year_edge)

    await service.get_latest_player_results(ZHENG.id, limit=1)

    assert provider.season_loads == [2027, 2026, 2025, 2024, 2023]


@pytest.mark.asyncio
async def test_get_player_results_last_scope_normalizes_limit_to_one() -> None:
    newest = _result("mat_new", datetime(2026, 8, 20, 10, 0, tzinfo=UTC))
    older = _result("mat_older", datetime(2026, 7, 1, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider({2026: (older, newest)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_player_results(ZHENG.id, "last", 5)

    assert results.scope == "last"
    assert results.availability is CapabilityStatus.AVAILABLE
    assert [match.id for match in results.matches] == ["mat_new"]


@pytest.mark.asyncio
async def test_get_player_results_recent_scope_uses_season_window() -> None:
    matches = tuple(
        _result(f"mat_{index}", datetime(2026, 5, 1 + index, 10, 0, tzinfo=UTC))
        for index in range(4)
    )
    provider = SeasonResultsProvider({2026: matches})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_player_results(ZHENG.id, "recent", 3)

    assert results.scope == "recent"
    assert results.availability is CapabilityStatus.AVAILABLE
    assert [match.id for match in results.matches] == ["mat_3", "mat_2", "mat_1"]
    assert provider.calls["live"] == 0
    assert provider.calls["fixtures"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["last", "recent"])
async def test_chat_history_is_partial_when_a_singles_result_is_undated(scope: str) -> None:
    undated = _result("mat_undated", None)
    dated = _result("mat_dated", datetime(2026, 5, 1, 10, 0, tzinfo=UTC))
    provider = SeasonResultsProvider({2026: (undated, dated)})
    service = build_service(provider, MemoryPlayerDirectoryRepository())

    results = await service.get_player_results(ZHENG.id, scope, 1)

    assert results.availability is CapabilityStatus.PARTIAL
    assert [match.id for match in results.matches] == [dated.id]


# --------------------------------------------- T54 profile-only season records


@pytest.mark.asyncio
async def test_season_record_defaults_to_current_year_and_uses_profile_cache(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    service = build_service(provider, seeded_directory)

    season, record = await service.get_player_season_record(ZHENG.id)
    assert season == 2026
    assert record is not None
    assert record.matches_won == 30

    await service.get_player_season_record(ZHENG.id)
    assert provider.calls["profile"] == 1
    assert provider.calls["live"] == 0
    assert provider.calls["fixtures"] == 0
    assert provider.calls["results"] == 0


@pytest.mark.asyncio
async def test_season_record_rejects_out_of_window_before_profile_access(
    seeded_directory,
) -> None:
    provider = ProfileProvider()
    service = build_service(provider, seeded_directory)

    for invalid_season in (2021, 2027):
        with pytest.raises(AppError) as failure:
            await service.get_player_season_record(ZHENG.id, season=invalid_season)
        assert failure.value.code == "invalid_request"
    assert provider.calls["profile"] == 0


@pytest.mark.asyncio
async def test_season_record_zero_match_record_is_not_unavailable(
    seeded_directory,
) -> None:
    class ZeroSeasonProvider(ProfileProvider):
        async def get_player_profile(self, player_id: str) -> PlayerProfileData:
            return PlayerProfileData(
                player=ZHENG,
                seasons=(
                    PlayerSeasonRecord(
                        season=2025, matches_won=0, matches_lost=0, titles=0
                    ),
                ),
            )

    service = build_service(ZeroSeasonProvider(), seeded_directory)

    season, record = await service.get_player_season_record(ZHENG.id, season=2025)
    assert season == 2025
    assert record is not None
    assert record.matches_won == 0

    missing_season, missing = await service.get_player_season_record(
        ZHENG.id, season=2024
    )
    assert missing_season == 2024
    assert missing is None


@pytest.mark.asyncio
async def test_season_record_uses_beijing_calendar_year() -> None:
    new_year_edge = datetime(2026, 12, 31, 18, 0, tzinfo=UTC)
    provider = ProfileProvider()
    service = build_service_with_now(provider, new_year_edge)

    season, record = await service.get_player_season_record(SINNER.id)

    assert season == 2027
    assert record is None  # the supplier fixture has no 2027 record yet
