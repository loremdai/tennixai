"""P2 service: catalog filters/sort/facets and bounded history/H2H."""

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
from app.service import MatchFilters, TennisService, catalog_sort_key
from p2_fakes import P2_NOW, CatalogFakeProvider


@pytest.fixture()
def service(catalog_provider: CatalogFakeProvider) -> TennisService:
    cache: AsyncTTLCache[str, object] = AsyncTTLCache(max_entries=256)
    return TennisService(
        catalog_provider, cache, now=lambda: P2_NOW, timezone="Asia/Macau"
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
async def test_yesterday_results_use_macau_calendar(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    yesterday_noon_utc = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    today_early_utc = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)
    older = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    catalog_provider.recent_results = [
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
async def test_recent_results_sorted_desc_and_limited(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    now_utc = P2_NOW
    catalog_provider.recent_results = [
        catalog_provider.finished_match("old", now_utc - timedelta(days=5)),
        catalog_provider.finished_match("newest", now_utc - timedelta(hours=6)),
        catalog_provider.finished_match("middle", now_utc - timedelta(days=2)),
    ]
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="recent", limit=2)

    assert results.availability is CapabilityStatus.AVAILABLE
    assert [match.id for match in results.matches] == [
        "mat_hist_newest",
        "mat_hist_middle",
    ]


@pytest.mark.asyncio
async def test_recent_results_are_partial_when_fetch_window_truncated(
    service: TennisService, catalog_provider: CatalogFakeProvider
) -> None:
    catalog_provider.recent_results = [
        catalog_provider.finished_match(f"m{i}", P2_NOW - timedelta(days=i))
        for i in range(10)
    ]
    sinner = await _sinner_id(catalog_provider)

    results = await service.get_player_results(sinner, scope="recent", limit=3)

    assert results.availability is CapabilityStatus.PARTIAL
    assert len(results.matches) == 3


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

    await service.get_player_results(sinner, scope="recent", limit=5)
    await service.get_player_results(sinner, scope="recent", limit=5)
    assert catalog_provider.recent_calls == 1

    await service.get_head_to_head(sinner, ruud, limit=5)
    await service.get_head_to_head(sinner, ruud, limit=2)
    assert catalog_provider.h2h_calls == 1

    # Empty responses are still cached (negative TTL), not refetched.
    catalog_provider.recent_results = []
    catalog_provider.recent_calls = 0
    await service.get_player_results(ruud, scope="recent", limit=5)
    await service.get_player_results(ruud, scope="recent", limit=5)
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
