"""P2 service: catalog filters/sort/facets and bounded history/H2H."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.cache import AsyncTTLCache
from app.domain import (
    CapabilityStatus,
    CircuitTier,
    Discipline,
    Gender,
    MatchStatus,
)
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.sync import DirectorySeeder, PlayerDirectorySync
from app.providers.fake import FakeTennisProvider
from app.service import MatchFilters, TennisService, catalog_sort_key
from p2_fakes import P2_NOW, CatalogFakeProvider


@pytest.fixture()
def service(catalog_provider: CatalogFakeProvider) -> TennisService:
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    return TennisService(
        catalog_provider, cache, now=lambda: P2_NOW, timezone="Asia/Shanghai"
    )


async def _sinner_id(provider: CatalogFakeProvider) -> str:
    return (await provider.search_players("sinner"))[0].id


async def _ruud_id(provider: CatalogFakeProvider) -> str:
    return (await provider.search_players("ruud"))[0].id


def test_default_filters_match_approved_defaults() -> None:
    filters = MatchFilters.default()
    assert filters.circuits == (CircuitTier.ATP, CircuitTier.WTA)
    assert filters.genders == ()
    assert filters.disciplines == (Discipline.SINGLES,)


@pytest.mark.asyncio
async def test_default_catalog_prefers_top_tour_singles(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog = await service.list_catalog(
        status="upcoming", filters=MatchFilters.default()
    )

    assert catalog.filters.circuits == (CircuitTier.ATP, CircuitTier.WTA)
    assert catalog.filters.disciplines == (Discipline.SINGLES,)
    assert all(
        item.tournament.circuit in {CircuitTier.ATP, CircuitTier.WTA}
        for item in catalog.matches
    )
    assert all(
        item.tournament.discipline is Discipline.SINGLES for item in catalog.matches
    )
    assert {match.id for match in catalog.matches} == {
        catalog_provider.sinner_alcaraz.id,
        catalog_provider.wta_upcoming.id,
    }
    assert catalog.featured_match_id == catalog.matches[0].id
    # Earlier scheduled top-tier match is featured.
    assert catalog.matches[0].id == catalog_provider.sinner_alcaraz.id


@pytest.mark.asyncio
async def test_first_catalog_read_seeds_rankings_before_hydrating_match_players() -> None:
    identities = MemoryIdentityRepository()
    provider = await FakeTennisProvider.create(identities, now=lambda: P2_NOW)
    directory = MemoryPlayerDirectoryRepository()
    seeder = DirectorySeeder(
        PlayerDirectorySync(provider, directory, now=lambda: P2_NOW)
    )
    service = TennisService(
        provider,
        AsyncTTLCache(max_entries=32),
        now=lambda: P2_NOW,
        timezone="Asia/Shanghai",
        directory=directory,
        seeder=seeder.ensure,
    )

    catalog = await service.list_catalog(status="live")

    sinner = next(player for match in catalog.matches for player in match.players if player.name == "Jannik Sinner")
    assert sinner.ranking == 1


@pytest.mark.asyncio
async def test_concurrent_service_seed_callers_wait_for_the_active_seed(
    catalog_provider: CatalogFakeProvider,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def seed() -> None:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()

    service = TennisService(
        catalog_provider,
        AsyncTTLCache(max_entries=8),
        now=lambda: P2_NOW,
        timezone="Asia/Shanghai",
        seeder=seed,
    )
    first = asyncio.create_task(service._ensure_seeded())
    await started.wait()
    second = asyncio.create_task(service._ensure_seeded())
    await asyncio.sleep(0)
    second_waited = not second.done()

    release.set()
    await asyncio.gather(first, second)

    assert second_waited
    assert calls == 1


@pytest.mark.asyncio
async def test_catalog_uses_default_filters_when_omitted(service: TennisService) -> None:
    catalog = await service.list_catalog(status="upcoming")
    assert catalog.filters == MatchFilters.default()


@pytest.mark.asyncio
async def test_catalog_sort_is_tier_then_live_then_time_then_id(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    all_filters = MatchFilters(circuits=(), genders=(), disciplines=())
    live_catalog = await service.list_catalog(status="live", filters=all_filters)
    assert [match.id for match in live_catalog.matches] == [
        catalog_provider.live_match.id,  # ATP live, scheduled 2026-09-08T10:00Z
        catalog_provider.wta_live.id,  # WTA live, scheduled 2026-09-09T10:00Z
    ]

    upcoming_catalog = await service.list_catalog(
        status="upcoming", filters=all_filters
    )
    ids = [match.id for match in upcoming_catalog.matches]
    assert ids == [
        catalog_provider.sinner_alcaraz.id,  # atp, 09-08
        catalog_provider.wta_upcoming.id,  # wta, 09-10
        catalog_provider.challenger_upcoming.id,  # challenger, 09-11
        catalog_provider.itf_doubles_upcoming.id,  # itf, 09-12
        catalog_provider.other_upcoming.id,  # other, 09-13
    ]

    # Tier beats live status in the canonical sort key (plan T24 step 2).
    atp_upcoming = catalog_provider.sinner_alcaraz
    challenger_live = catalog_provider.wta_live.model_copy(
        update={"tournament": catalog_provider.challenger_upcoming.tournament}
    )
    assert catalog_sort_key(atp_upcoming) < catalog_sort_key(challenger_live)


@pytest.mark.asyncio
async def test_stacked_filters_select_exact_facet_combination(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog = await service.list_catalog(
        status="upcoming",
        filters=MatchFilters(
            circuits=(CircuitTier.ITF,),
            genders=(Gender.WOMEN,),
            disciplines=(Discipline.DOUBLES,),
        ),
    )
    assert [match.id for match in catalog.matches] == [
        catalog_provider.itf_doubles_upcoming.id
    ]
    assert catalog.featured_match_id == catalog_provider.itf_doubles_upcoming.id


@pytest.mark.asyncio
async def test_empty_filter_group_means_all(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog = await service.list_catalog(
        status="upcoming",
        filters=MatchFilters(circuits=(), genders=(), disciplines=()),
    )
    assert len(catalog.matches) == 5


@pytest.mark.asyncio
async def test_facet_counts_respect_other_groups_and_keep_zero_values(
    service: TennisService,
) -> None:
    catalog = await service.list_catalog(
        status="upcoming", filters=MatchFilters.default()
    )

    assert catalog.facet_counts.circuits == {
        "atp": 1,
        "wta": 1,
        "challenger": 1,  # singles men: passes gender+discipline groups
        "itf": 0,  # doubles: excluded by the active discipline filter
        "other": 0,  # unknown discipline: excluded
    }
    assert catalog.facet_counts.genders == {
        "men": 1,  # only within active circuits atp+wta
        "women": 1,
        "mixed": 0,
        "unknown": 0,
    }
    assert catalog.facet_counts.disciplines == {
        "singles": 2,
        "doubles": 0,
        "team": 0,
        "unknown": 0,
    }


@pytest.mark.asyncio
async def test_catalog_rejects_invalid_status(service: TennisService) -> None:
    with pytest.raises(AppError) as error_info:
        await service.list_catalog(status="finished")
    assert error_info.value.code == "invalid_request"
    assert error_info.value.status_code == 422


@pytest.mark.asyncio
async def test_yesterday_results_use_beijing_calendar(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    yesterday_noon_utc = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    today_early_utc = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)
    older = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    doubles_yesterday = catalog_provider.finished_match(
        "yesterday_doubles", yesterday_noon_utc + timedelta(hours=1)
    ).model_copy(update={"tournament": catalog_provider.itf_doubles_upcoming.tournament})
    catalog_provider.recent_results = [
        doubles_yesterday,
        catalog_provider.finished_match("yesterday", yesterday_noon_utc),
        catalog_provider.finished_match("today", today_early_utc),
        catalog_provider.finished_match("older", older),
    ]
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="yesterday", limit=5)

    assert results.availability is CapabilityStatus.AVAILABLE
    assert [match.id for match in results.matches] == ["mat_hist_yesterday"]
    assert results.scope == "yesterday"
    assert results.player_id == sinner


@pytest.mark.asyncio
async def test_yesterday_history_is_partial_when_a_singles_result_is_undated(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog_provider.recent_results = [
        catalog_provider.finished_match("undated_yesterday", None)
    ]
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="yesterday", limit=5)

    assert results.availability is CapabilityStatus.PARTIAL
    assert results.matches == ()


@pytest.mark.asyncio
async def test_recent_history_excludes_newer_doubles_result(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)
    newest_doubles = catalog_provider.finished_match(
        "newest_doubles", P2_NOW - timedelta(hours=1)
    ).model_copy(update={"tournament": catalog_provider.itf_doubles_upcoming.tournament})
    older_singles = catalog_provider.finished_match(
        "older_singles", P2_NOW - timedelta(hours=2)
    )
    catalog_provider.finished_results += (newest_doubles, older_singles)

    results = await service.get_player_results(sinner, scope="recent", limit=1)

    assert [match.id for match in results.matches] == [older_singles.id]


@pytest.mark.asyncio
async def test_yesterday_results_are_partial_when_provider_window_hits_fetch_limit(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    yesterday = catalog_provider.finished_match(
        "yesterday_at_fetch_boundary", datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    )
    today = [
        catalog_provider.finished_match(
            f"today_{index}", P2_NOW - timedelta(minutes=index + 1)
        )
        for index in range(9)
    ]
    catalog_provider.recent_results = [yesterday, *today]
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="yesterday", limit=5)

    assert results.availability is CapabilityStatus.PARTIAL
    assert [match.id for match in results.matches] == [yesterday.id]


@pytest.mark.asyncio
async def test_recent_results_use_season_window_not_fetch_window(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)
    # The bounded 30-day fetch window is no longer the recent-scope source.
    catalog_provider.recent_results = [
        catalog_provider.finished_match("newest", P2_NOW - timedelta(hours=6)),
    ]

    results = await service.get_player_results(sinner, scope="recent", limit=2)

    assert catalog_provider.recent_calls == 0
    assert results.availability is CapabilityStatus.AVAILABLE
    assert len(results.matches) == 2
    assert all(match.status is MatchStatus.FINISHED for match in results.matches)
    expected = sorted(
        (
            match
            for match in catalog_provider.finished_results
            if any(player.id == sinner for player in match.players)
        ),
        key=lambda match: (match.scheduled_at, match.id),
        reverse=True,
    )[:2]
    assert [match.id for match in results.matches] == [
        match.id for match in expected
    ]


@pytest.mark.asyncio
async def test_last_scope_returns_exactly_one_newest_finished(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="last", limit=5)

    assert results.scope == "last"
    assert results.availability is CapabilityStatus.AVAILABLE
    assert len(results.matches) == 1
    assert results.matches[0].status is MatchStatus.FINISHED
    assert catalog_provider.recent_calls == 0


@pytest.mark.asyncio
async def test_results_limit_bounds_are_enforced(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)
    for invalid_limit in (0, 11):
        with pytest.raises(AppError) as error_info:
            await service.get_player_results(sinner, scope="recent", limit=invalid_limit)
        assert error_info.value.code == "invalid_request"
        with pytest.raises(AppError):
            await service.get_head_to_head(sinner, sinner, limit=invalid_limit)


@pytest.mark.asyncio
async def test_unsupported_history_reports_unavailable_not_zero(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog_provider.recent_error = AppError(
        "unsupported", "Backup adapter", 501
    )
    catalog_provider.h2h_error = AppError("unsupported", "Backup adapter", 501)
    sinner = await _sinner_id(catalog_provider)
    ruud = await _ruud_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="yesterday", limit=5)
    assert results.availability is CapabilityStatus.UNAVAILABLE
    assert results.matches == ()

    head_to_head = await service.get_head_to_head(sinner, ruud, limit=5)
    assert head_to_head.availability is CapabilityStatus.UNAVAILABLE
    assert head_to_head.head_to_head is None


@pytest.mark.asyncio
async def test_unknown_player_propagates_not_found(
    service: TennisService,
) -> None:
    with pytest.raises(AppError) as error_info:
        await service.get_player_results("ply_missing", scope="recent", limit=5)
    assert error_info.value.code == "not_found"
    assert error_info.value.status_code == 404

    with pytest.raises(AppError):
        await service.get_head_to_head("ply_missing", "ply_other", limit=5)


@pytest.mark.asyncio
async def test_history_and_h2h_are_cached_with_negative_ttl(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)
    ruud = await _ruud_id(catalog_provider)
    catalog_provider.recent_results = [
        catalog_provider.finished_match("y", P2_NOW - timedelta(days=1, hours=4))
    ]
    catalog_provider.h2h_meetings = [
        catalog_provider.finished_match("h", P2_NOW - timedelta(days=3))
    ]

    # `yesterday` is the only remaining consumer of the bounded recent fetch
    # and its negative-TTL cache; `recent`/`last` now use the season window.
    await service.get_player_results(sinner, scope="yesterday", limit=5)
    await service.get_player_results(sinner, scope="yesterday", limit=5)
    assert catalog_provider.recent_calls == 1

    await service.get_head_to_head(sinner, ruud, limit=5)
    await service.get_head_to_head(sinner, ruud, limit=2)
    assert catalog_provider.h2h_calls == 1

    # Empty responses are still cached (negative TTL), not refetched.
    catalog_provider.recent_results = []
    catalog_provider.recent_calls = 0
    await service.get_player_results(ruud, scope="yesterday", limit=5)
    await service.get_player_results(ruud, scope="yesterday", limit=5)
    assert catalog_provider.recent_calls == 1


@pytest.mark.asyncio
async def test_head_to_head_preserves_orientation_and_limits(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    sinner = await _sinner_id(catalog_provider)
    ruud = await _ruud_id(catalog_provider)
    catalog_provider.h2h_meetings = [
        catalog_provider.finished_match(f"h{i}", P2_NOW - timedelta(days=i + 1))
        for i in range(3)
    ]
    catalog_provider.h2h_first_recent = [
        catalog_provider.finished_match("f0", P2_NOW - timedelta(days=1))
    ]
    catalog_provider.h2h_second_recent = [
        catalog_provider.finished_match("s0", P2_NOW - timedelta(days=2))
    ]

    result = await service.get_head_to_head(sinner, ruud, limit=2)

    assert result.availability is CapabilityStatus.AVAILABLE
    assert result.head_to_head is not None
    assert result.head_to_head.first_player_id == sinner
    assert result.head_to_head.second_player_id == ruud
    assert len(result.head_to_head.meetings) == 2
    assert len(result.head_to_head.first_player_recent) == 1
    assert len(result.head_to_head.second_player_recent) == 1


@pytest.mark.parametrize(
    "capped_collection",
    ("h2h_meetings", "h2h_first_recent", "h2h_second_recent"),
)
@pytest.mark.asyncio
async def test_head_to_head_is_partial_when_any_collection_reaches_fetch_limit(
    capped_collection: str,
    service: TennisService,
    catalog_provider: CatalogFakeProvider,
) -> None:
    sinner = await _sinner_id(catalog_provider)
    ruud = await _ruud_id(catalog_provider)
    history = [
        catalog_provider.finished_match(
            f"{capped_collection}_{index}", P2_NOW - timedelta(days=index + 1)
        )
        for index in range(10)
    ]
    setattr(catalog_provider, capped_collection, history)

    result = await service.get_head_to_head(sinner, ruud, limit=10)

    assert result.availability is CapabilityStatus.PARTIAL


@pytest.mark.parametrize(
    ("provider_attribute", "field"),
    [
        ("h2h_meetings_may_be_truncated", "meetings_may_be_truncated"),
        (
            "h2h_first_recent_may_be_truncated",
            "first_player_recent_may_be_truncated",
        ),
        (
            "h2h_second_recent_may_be_truncated",
            "second_player_recent_may_be_truncated",
        ),
    ],
)
@pytest.mark.asyncio
async def test_head_to_head_respects_provider_truncation_with_unmappable_rows(
    provider_attribute: str,
    field: str,
    service: TennisService,
    catalog_provider: CatalogFakeProvider,
) -> None:
    sinner = await _sinner_id(catalog_provider)
    ruud = await _ruud_id(catalog_provider)
    catalog_provider.h2h_meetings = [
        catalog_provider.finished_match(f"h{i}", P2_NOW - timedelta(days=i + 1))
        for i in range(9)
    ]
    setattr(catalog_provider, provider_attribute, True)

    result = await service.get_head_to_head(sinner, ruud, limit=10)

    assert result.availability is CapabilityStatus.PARTIAL
    assert result.head_to_head is not None
    assert getattr(result.head_to_head, field) is True


@pytest.mark.asyncio
async def test_live_matches_still_flow_through_p1_path(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    matches = await service.list_matches("live")
    assert {match.id for match in matches} == {
        catalog_provider.live_match.id,
        catalog_provider.wta_live.id,
    }
    assert all(match.status is MatchStatus.LIVE for match in matches)
