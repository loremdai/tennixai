from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from app.cache import AsyncTTLCache
from app.domain import (
    CapabilityStatus,
    DataFreshness,
    DataQuality,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatus,
    MomentumObservation,
    Player,
    SetScore,
    Tournament,
)
from app.errors import AppError
from app.service import MatchTimeScope, TennisService, tonight_window

UTC = timezone.utc
NOW_UTC = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)  # 20:00 Asia/Macau

SINNER = Player(id="ply_s", name="Jannik Sinner")
SINNER_SHORT = Player(id="ply_short", name="Sinner")
ALCARAZ = Player(id="ply_a", name="Carlos Alcaraz")
JONES = Player(id="ply_j", name="Jannik Jones")
DJOKOVIC_RANKED = Player(id="ply_d_ranked", name="Novak Djokovic", ranking=3)
DJOKOVIC_DUPLICATE = Player(id="ply_d_duplicate", name="Novak Djokovic")
DJOKOVIC_TEAM = Player(id="ply_d_team", name="Novak Djokovic / Casper Ruud")


class UtcClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class NumericClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingProvider:
    def __init__(
        self,
        *,
        players: list[Player] | None = None,
        live: list[Match] | None = None,
        upcoming: list[Match] | None = None,
        matches: dict[str, Match] | None = None,
        profiles: dict[str, Player] | None = None,
        snapshots: dict[str, MatchSnapshot] | None = None,
    ) -> None:
        self.players = players or []
        self.live = live or []
        self.upcoming = upcoming or []
        self.matches = matches or {}
        self.profiles = profiles or {}
        self.snapshots = snapshots or {}
        self.calls: Counter[str] = Counter()
        self.list_failure: AppError | None = None
        self.detail_failure: AppError | None = None

    async def search_players(self, query: str) -> list[Player]:
        self.calls["search_players"] += 1
        normalized = query.strip().casefold()
        return [
            player for player in self.players if normalized in player.name.casefold()
        ]

    async def get_live_matches(self, *, player_id: str | None = None) -> list[Match]:
        self.calls["get_live_matches"] += 1
        if self.list_failure is not None:
            raise self.list_failure
        return self._filter(self.live, player_id)

    async def get_fixtures(self, *, player_id: str | None = None) -> list[Match]:
        self.calls["get_fixtures"] += 1
        if self.list_failure is not None:
            raise self.list_failure
        return self._filter(self.upcoming, player_id)

    async def get_match(self, match_id: str) -> Match:
        self.calls["get_match"] += 1
        if self.detail_failure is not None:
            raise self.detail_failure
        match = self.matches.get(match_id)
        if match is None:
            raise AppError("not_found", "Match not found", 404)
        return match

    async def get_player(self, player_id: str) -> Player:
        self.calls["get_player"] += 1
        profile = self.profiles.get(player_id)
        if profile is None:
            raise AppError("not_found", "Player not found", 404)
        return profile

    async def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        self.calls["get_match_snapshot"] += 1
        snapshot = self.snapshots.get(match_id)
        if snapshot is None:
            raise AppError("not_found", "Match not found", 404)
        return snapshot

    async def get_score(self, match_id: str) -> LiveMatchState:
        self.calls["get_score"] += 1
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


class MemorySnapshotStore:
    def __init__(self, snapshot: MatchSnapshot) -> None:
        self.snapshot = snapshot
        self.saved = []

    async def load_snapshot(self, match_id: str) -> MatchSnapshot | None:
        return self.snapshot if self.snapshot.match.id == match_id else None

    async def save_reduction(self, reduction) -> None:
        self.saved.append(reduction)
        self.snapshot = reduction.snapshot


def build_match(
    match_id: str,
    status: MatchStatus,
    scheduled_at: datetime | None,
    players: tuple[Player, Player] = (SINNER, ALCARAZ),
) -> Match:
    live_state = None
    if status is MatchStatus.LIVE:
        live_state = LiveMatchState(
            score=MatchScore(
                sets_won=(1, 0),
                sets=(SetScore(number=1, player1_games=6, player2_games=4),),
                points=("0", "15"),
            ),
            server_player_id=players[0].id,
        )
    return Match(
        id=match_id,
        status=status,
        players=players,
        tournament=Tournament(id="trn_1", name="ATP Finals", tour="atp"),
        scheduled_at=scheduled_at,
        live_state=live_state,
        freshness=DataFreshness(
            provider="fake", observed_at=scheduled_at or NOW_UTC
        ),
    )


def build_service(
    provider: CountingProvider,
    now: datetime = NOW_UTC,
    *,
    snapshots=None,
) -> tuple[TennisService, UtcClock, NumericClock]:
    utc_clock = UtcClock(now)
    numeric_clock = NumericClock()
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256, now=numeric_clock)
    service = TennisService(
        provider,
        cache,
        now=utc_clock,
        timezone="Asia/Macau",
        snapshots=snapshots,
    )
    return service, utc_clock, numeric_clock


@pytest.fixture()
def selection_provider() -> CountingProvider:
    m_past = build_match("mat_past", MatchStatus.SCHEDULED, datetime(2026, 9, 8, 2, 0, tzinfo=UTC))
    m_live = build_match("mat_live", MatchStatus.LIVE, datetime(2026, 9, 8, 10, 0, tzinfo=UTC))
    m_tonight = build_match("mat_tonight", MatchStatus.SCHEDULED, datetime(2026, 9, 8, 14, 0, tzinfo=UTC))
    m_tomorrow = build_match("mat_tomorrow", MatchStatus.SCHEDULED, datetime(2026, 9, 9, 12, 0, tzinfo=UTC))
    return CountingProvider(
        players=[SINNER],
        live=[m_live],
        upcoming=[m_past, m_tonight, m_tomorrow],
    )


@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        ("2026-09-08T02:00:00+08:00", "2026-09-07T18:00:00+08:00", "2026-09-08T06:00:00+08:00"),
        ("2026-09-08T12:00:00+08:00", "2026-09-08T18:00:00+08:00", "2026-09-09T06:00:00+08:00"),
        ("2026-09-08T20:00:00+08:00", "2026-09-08T18:00:00+08:00", "2026-09-09T06:00:00+08:00"),
    ],
)
def test_tonight_window(now: str, expected_start: str, expected_end: str) -> None:
    assert tonight_window(datetime.fromisoformat(now)) == (
        datetime.fromisoformat(expected_start),
        datetime.fromisoformat(expected_end),
    )


@pytest.mark.asyncio
async def test_empty_player_query_is_invalid_request() -> None:
    service, _, _ = build_service(CountingProvider(players=[SINNER]))

    with pytest.raises(AppError) as error_info:
        await service.search_players("   ")
    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_exact_case_insensitive_match_wins_over_substring() -> None:
    m_short = build_match(
        "mat_short", MatchStatus.SCHEDULED, NOW_UTC + timedelta(hours=2), (SINNER_SHORT, ALCARAZ)
    )
    m_full = build_match(
        "mat_full", MatchStatus.SCHEDULED, NOW_UTC + timedelta(hours=1), (SINNER, ALCARAZ)
    )
    provider = CountingProvider(
        players=[SINNER, SINNER_SHORT], upcoming=[m_full, m_short]
    )
    service, _, _ = build_service(provider)

    result = await service.find_player_matches("sinner", MatchTimeScope.NEXT)

    assert [match.id for match in result] == ["mat_short"]


@pytest.mark.asyncio
async def test_multiple_substring_matches_raise_ambiguous_player() -> None:
    provider = CountingProvider(players=[SINNER, JONES])
    service, _, _ = build_service(provider)

    with pytest.raises(AppError) as error_info:
        await service.find_player_matches("jannik", MatchTimeScope.NEXT)

    error = error_info.value
    assert error.code == "ambiguous_player"
    assert error.status_code == 409
    assert error.details["candidates"] == [
        {"id": "ply_s", "name": "Jannik Sinner"},
        {"id": "ply_j", "name": "Jannik Jones"},
    ]


@pytest.mark.asyncio
async def test_djokovic_resolution_ignores_duplicate_and_composite_candidates() -> None:
    match = build_match(
        "mat_djokovic",
        MatchStatus.LIVE,
        NOW_UTC,
        players=(DJOKOVIC_RANKED, ALCARAZ),
    )
    provider = CountingProvider(
        players=[DJOKOVIC_DUPLICATE, DJOKOVIC_TEAM, DJOKOVIC_RANKED],
        live=[match],
    )
    service, _, _ = build_service(provider)

    result = await service.list_matches("live", "Djokovic")

    assert [item.id for item in result] == ["mat_djokovic"]


@pytest.mark.asyncio
async def test_exact_player_resolution_trims_candidate_name() -> None:
    padded_sinner = Player(id="ply_padded", name=" Sinner ")
    match = build_match(
        "mat_padded_sinner",
        MatchStatus.LIVE,
        NOW_UTC,
        players=(padded_sinner, ALCARAZ),
    )
    provider = CountingProvider(
        players=[padded_sinner, SINNER],
        live=[match],
    )
    service, _, _ = build_service(provider)

    result = await service.list_matches("live", "Sinner")

    assert [item.id for item in result] == ["mat_padded_sinner"]


@pytest.mark.asyncio
async def test_unknown_player_raises_not_found() -> None:
    provider = CountingProvider(players=[SINNER])
    service, _, _ = build_service(provider)

    with pytest.raises(AppError) as error_info:
        await service.find_player_matches("Federer", MatchTimeScope.NEXT)
    assert error_info.value.code == "not_found"
    assert error_info.value.status_code == 404


@pytest.mark.asyncio
async def test_next_returns_earliest_future_non_terminal_match(
    selection_provider: CountingProvider,
) -> None:
    service, _, _ = build_service(selection_provider)

    result = await service.find_player_matches("Sinner", MatchTimeScope.NEXT)

    assert [match.id for match in result] == ["mat_tonight"]


@pytest.mark.asyncio
async def test_today_uses_macau_calendar_day_and_excludes_past_fixtures(
    selection_provider: CountingProvider,
) -> None:
    service, _, _ = build_service(selection_provider)

    result = await service.find_player_matches("Sinner", MatchTimeScope.TODAY)

    assert [match.id for match in result] == ["mat_live", "mat_tonight"]


@pytest.mark.asyncio
async def test_tonight_uses_night_window_and_keeps_live_matches(
    selection_provider: CountingProvider,
) -> None:
    service, _, _ = build_service(selection_provider)

    result = await service.find_player_matches("Sinner", MatchTimeScope.TONIGHT)

    assert [match.id for match in result] == ["mat_live", "mat_tonight"]


@pytest.mark.asyncio
async def test_list_matches_rejects_unknown_status() -> None:
    service, _, _ = build_service(CountingProvider(players=[SINNER]))

    with pytest.raises(AppError) as error_info:
        await service.list_matches("finished")
    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_live_list_is_cached_for_60_seconds() -> None:
    provider = CountingProvider(
        players=[SINNER],
        live=[build_match("mat_live", MatchStatus.LIVE, NOW_UTC)],
    )
    service, _, numeric = build_service(provider)

    await service.list_matches("live")
    numeric.advance(30)
    await service.list_matches("live")
    assert provider.calls["get_live_matches"] == 1

    numeric.advance(31)
    await service.list_matches("live")
    assert provider.calls["get_live_matches"] == 2


@pytest.mark.asyncio
async def test_live_list_stale_fallback_bounded_at_300_seconds() -> None:
    live_match = build_match("mat_live", MatchStatus.LIVE, NOW_UTC)
    provider = CountingProvider(players=[SINNER], live=[live_match])
    service, _, numeric = build_service(provider)

    await service.list_matches("live")
    numeric.advance(61)
    provider.list_failure = AppError("provider_unavailable", "down", 503)

    stale = await service.list_matches("live")
    assert [match.id for match in stale] == ["mat_live"]
    assert stale[0].freshness.is_stale is True
    assert stale[0].freshness.age_seconds == 61

    numeric.advance(240)  # age 301 > 300
    with pytest.raises(AppError) as error_info:
        await service.list_matches("live")
    assert error_info.value.code == "provider_unavailable"


@pytest.mark.asyncio
async def test_match_snapshot_hydrates_missing_player_profiles_once() -> None:
    match = build_match("mat_detail", MatchStatus.LIVE, NOW_UTC)
    snapshot = MatchSnapshot(match=match, state_version=0, as_of=NOW_UTC)
    provider = CountingProvider(
        snapshots={match.id: snapshot},
        profiles={
            SINNER.id: Player(id=SINNER.id, name="Jannik Sinner", ranking=1),
            ALCARAZ.id: Player(id=ALCARAZ.id, name="Carlos Alcaraz", ranking=2),
        },
    )
    service, _, _ = build_service(provider)

    first = await service.resolve_match_snapshot(match.id)
    second = await service.resolve_match_snapshot(match.id)

    assert [player.ranking for player in first.match.players] == [1, 2]
    assert [player.ranking for player in second.match.players] == [1, 2]
    assert provider.calls["get_player"] == 2


@pytest.mark.asyncio
async def test_match_snapshot_refreshes_and_persists_missing_match_metadata() -> None:
    stored_match = build_match("mat_metadata", MatchStatus.SCHEDULED, NOW_UTC)
    stored = MatchSnapshot(match=stored_match, state_version=0, as_of=NOW_UTC)
    provider_match = stored_match.model_copy(update={"surface": "hard"})
    provider_snapshot = MatchSnapshot(
        match=provider_match, state_version=0, as_of=NOW_UTC
    )
    provider = CountingProvider(snapshots={stored_match.id: provider_snapshot})
    store = MemorySnapshotStore(stored)
    service, _, _ = build_service(provider, snapshots=store)

    first = await service.resolve_match_snapshot(stored_match.id)
    second = await service.resolve_match_snapshot(stored_match.id)

    assert first.match.surface == "hard"
    assert second.match.surface == "hard"
    assert provider.calls["get_match_snapshot"] == 1
    assert len(store.saved) == 1
    assert store.saved[0].snapshot.match.surface == "hard"


@pytest.mark.asyncio
async def test_match_snapshot_normalizes_quality_for_persisted_momentum() -> None:
    match = build_match("mat_quality", MatchStatus.LIVE, NOW_UTC)
    snapshot = MatchSnapshot(
        match=match,
        momentum=(
            MomentumObservation(
                match_id=match.id,
                point_sequence=1,
                state_version=0,
                algorithm_version="recent-control-v1",
                value=12.5,
                leader_player_id=SINNER.id,
                as_of=NOW_UTC,
                input_summary="test",
            ),
        ),
        quality=(
            DataQuality(
                capability="momentum",
                status=CapabilityStatus.UNAVAILABLE,
                provider="api_tennis",
                reason="not_computed",
                observed_at=NOW_UTC,
            ),
        ),
        state_version=0,
        as_of=NOW_UTC,
    )
    provider = CountingProvider(snapshots={match.id: snapshot})
    service, _, _ = build_service(provider)

    resolved = await service.resolve_match_snapshot(match.id)

    momentum_quality = next(
        item for item in resolved.quality if item.capability == "momentum"
    )
    assert momentum_quality.status is CapabilityStatus.AVAILABLE
    assert momentum_quality.provider == "tennix"
    assert momentum_quality.reason is None


@pytest.mark.asyncio
async def test_upcoming_list_fresh_600_and_stale_bounded_at_1800() -> None:
    upcoming = build_match("mat_up", MatchStatus.SCHEDULED, NOW_UTC + timedelta(hours=2))
    provider = CountingProvider(players=[SINNER], upcoming=[upcoming])
    service, _, numeric = build_service(provider)

    await service.list_matches("upcoming")
    numeric.advance(599)
    await service.list_matches("upcoming")
    assert provider.calls["get_fixtures"] == 1

    numeric.advance(2)  # age 601 > 600
    provider.list_failure = AppError("provider_unavailable", "down", 503)
    stale = await service.list_matches("upcoming")
    assert stale[0].freshness.is_stale is True
    assert stale[0].freshness.age_seconds == 601

    numeric.advance(1200)  # age 1801 > 1800
    with pytest.raises(AppError):
        await service.list_matches("upcoming")


@pytest.mark.asyncio
async def test_player_search_ttl_is_one_hour_without_stale_fallback() -> None:
    provider = CountingProvider(players=[SINNER])
    service, _, numeric = build_service(provider)

    await service.search_players("Sinner")
    numeric.advance(3599)
    await service.search_players("sinner")  # casefolded key hits the same entry
    assert provider.calls["search_players"] == 1

    numeric.advance(2)  # age 3601 > 3600, stale_ttl is 0
    provider.list_failure = None
    await service.search_players("Sinner")
    assert provider.calls["search_players"] == 2


@pytest.mark.asyncio
async def test_empty_player_search_is_reused_for_30_seconds() -> None:
    provider = CountingProvider(players=[SINNER])
    service, _, numeric = build_service(provider)

    assert await service.search_players("nobody") == []
    numeric.advance(29)
    assert await service.search_players("nobody") == []
    assert provider.calls["search_players"] == 1

    numeric.advance(2)  # age 31 > 30
    assert await service.search_players("nobody") == []
    assert provider.calls["search_players"] == 2


@pytest.mark.asyncio
async def test_get_match_live_detail_cached_60_seconds_and_stale_marked() -> None:
    live_match = build_match("mat_live", MatchStatus.LIVE, NOW_UTC)
    provider = CountingProvider(matches={"mat_live": live_match})
    service, _, numeric = build_service(provider)

    first = await service.get_match("mat_live")
    numeric.advance(59)
    second = await service.get_match("mat_live")
    assert provider.calls["get_match"] == 1
    assert first.freshness.is_stale is False
    assert second.freshness.is_stale is False

    numeric.advance(2)  # age 61 > 60
    provider.detail_failure = AppError("provider_unavailable", "down", 503)
    stale = await service.get_match("mat_live")
    assert stale.freshness.is_stale is True
    assert stale.freshness.age_seconds == 61

    numeric.advance(240)  # age 301 > 300
    with pytest.raises(AppError):
        await service.get_match("mat_live")


@pytest.mark.asyncio
async def test_get_match_scheduled_detail_cached_600_seconds() -> None:
    match = build_match("mat_up", MatchStatus.SCHEDULED, NOW_UTC + timedelta(hours=2))
    provider = CountingProvider(matches={"mat_up": match})
    service, _, numeric = build_service(provider)

    await service.get_match("mat_up")
    numeric.advance(599)
    await service.get_match("mat_up")
    assert provider.calls["get_match"] == 1

    numeric.advance(2)
    await service.get_match("mat_up")
    assert provider.calls["get_match"] == 2


@pytest.mark.asyncio
async def test_unknown_match_negative_cache_for_30_seconds() -> None:
    provider = CountingProvider(matches={})
    service, _, numeric = build_service(provider)

    with pytest.raises(AppError) as error_info:
        await service.get_match("mat_missing")
    assert error_info.value.code == "not_found"

    numeric.advance(29)
    with pytest.raises(AppError):
        await service.get_match("mat_missing")
    assert provider.calls["get_match"] == 1

    numeric.advance(2)  # age 31 > 30
    with pytest.raises(AppError):
        await service.get_match("mat_missing")
    assert provider.calls["get_match"] == 2
