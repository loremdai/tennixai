"""Exact market-to-match mapping tests (T59).

Mapping is strict: both outcome names must resolve through the shared
PlayerResolver to internal IDs, the unordered player pair must match exactly
one candidate match, the schedule must sit inside the bounded tolerance and
the event context must not conflict. Fuzzy scores, LLM judgement and manual
permanent bindings are never the final authority.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain import (
    DataFreshness,
    Discipline,
    Gender,
    Match,
    MatchStatus,
    Player,
    Tournament,
)
from app.markets.mapping import (
    LinkDecision,
    MappingResult,
    MappingStatus,
    evaluate_link_change,
    map_market,
)
from app.markets.models import Market, MarketOutcome, MarketStatus
from app.players.enrichment import derive_chinese_aliases
from app.players.models import RankingEntry, RankingMovement, Tour
from app.players.normalization import derive_english_aliases
from app.players.repository import MemoryPlayerDirectoryRepository
from app.players.resolver import PlayerResolver

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
EVENT_START = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def _rank(player_id: str, name: str, rank: int, tour: Tour = Tour.ATP) -> RankingEntry:
    return RankingEntry(
        player=Player(id=player_id, name=name, ranking=rank),
        tour=tour,
        rank=rank,
        points=1000,
        movement=RankingMovement.SAME,
        ranking_date=NOW.date(),
        fetched_at=NOW,
    )


@pytest.fixture()
async def resolver() -> PlayerResolver:
    repository = MemoryPlayerDirectoryRepository()
    await repository.save_ranking_snapshot(
        (
            _rank("ply_alpha", "Alpha One", 10),
            _rank("ply_beta", "Beta Two", 20),
            _rank("ply_gamma", "Gamma Three", 30),
        )
    )
    for directory_player in await repository.list_players_for_alias_sync(limit=100):
        await repository.upsert_aliases(derive_english_aliases(directory_player))
    await repository.upsert_aliases(
        derive_chinese_aliases("ply_alpha", "阿尔法一号", model="test-model")
    )
    return PlayerResolver(repository)


def make_market(
    *,
    player_a: str = "ply_alpha",
    player_b: str = "ply_beta",
    name_a: str = "Alpha One",
    name_b: str = "Beta Two",
    event_start: datetime | None = EVENT_START,
) -> Market:
    return Market(
        id="mkt_map_1",
        question=f"{name_a} vs. {name_b}: Match Winner",
        outcomes=(
            MarketOutcome(player_id=player_a, name=name_a),
            MarketOutcome(player_id=player_b, name=name_b),
        ),
        status=MarketStatus.OPEN,
        rules_version=1,
        event_start=event_start,
        provider="polymarket",
        observed_at=NOW,
    )


def make_match(
    match_id: str,
    *,
    player_a: str = "ply_alpha",
    player_b: str = "ply_beta",
    scheduled_at: datetime | None = EVENT_START,
    status: MatchStatus = MatchStatus.SCHEDULED,
    discipline: Discipline = Discipline.SINGLES,
) -> Match:
    return Match(
        id=match_id,
        status=status,
        players=(
            Player(id=player_a, name="A"),
            Player(id=player_b, name="B"),
        ),
        tournament=Tournament(
            id="trn_1",
            name="Test Open",
            tour="atp",
            discipline=discipline,
            gender=Gender.MEN,
        ),
        scheduled_at=scheduled_at,
        freshness=DataFreshness(provider="test", observed_at=NOW),
    )


async def test_exact_unordered_pair_maps_to_internal_match(resolver):
    # Match lists the players in reversed order; the pair is unordered.
    match = make_match("mat_internal", player_a="ply_beta", player_b="ply_alpha")

    result = await map_market(make_market(), (match,), resolver)

    assert result.status is MappingStatus.MAPPED
    assert result.match_id == "mat_internal"
    assert set(result.player_ids or ()) == {"ply_alpha", "ply_beta"}


async def test_bilingual_market_names_resolve_to_same_pair(resolver):
    market = make_market(name_a="阿尔法一号", name_b="Beta Two")
    match = make_match("mat_internal")

    result = await map_market(market, (match,), resolver)

    assert result.status is MappingStatus.MAPPED
    assert result.match_id == "mat_internal"


async def test_schedule_tolerance_is_forty_five_minutes(resolver):
    match_inside = make_match(
        "mat_inside", scheduled_at=EVENT_START + timedelta(minutes=44)
    )
    match_outside = make_match(
        "mat_outside", scheduled_at=EVENT_START + timedelta(minutes=46)
    )

    inside = await map_market(make_market(), (match_inside,), resolver)
    outside = await map_market(make_market(), (match_outside,), resolver)

    assert inside.status is MappingStatus.MAPPED
    assert outside.status is MappingStatus.OUT_OF_WINDOW
    assert outside.reason == "schedule_outside_window"


async def test_live_match_without_schedule_time_still_maps(resolver):
    match = make_match("mat_live", scheduled_at=None, status=MatchStatus.LIVE)

    result = await map_market(make_market(), (match,), resolver)

    assert result.status is MappingStatus.MAPPED
    assert result.match_id == "mat_live"


async def test_duplicate_candidates_are_ambiguous(resolver):
    matches = (
        make_match("mat_one", scheduled_at=EVENT_START),
        make_match("mat_two", scheduled_at=EVENT_START + timedelta(minutes=10)),
    )

    result = await map_market(make_market(), matches, resolver)

    assert result.status is MappingStatus.AMBIGUOUS
    assert result.match_id is None
    assert result.reason == "multiple_pair_candidates"


async def test_unresolved_player_never_maps(resolver):
    market = make_market(player_a="ply_ghost", name_a="Ghost Player")

    result = await map_market(market, (make_match("mat_internal"),), resolver)

    assert result.status is MappingStatus.UNRESOLVED_PLAYER
    assert result.match_id is None
    assert result.reason and "unresolved" in result.reason


async def test_mismatched_pair_does_not_map(resolver):
    market = make_market(player_b="ply_gamma", name_b="Gamma Three")

    result = await map_market(market, (make_match("mat_internal"),), resolver)

    assert result.status is MappingStatus.NO_MATCH
    assert result.match_id is None


async def test_doubles_context_conflict_is_excluded(resolver):
    match = make_match("mat_doubles", discipline=Discipline.DOUBLES)

    result = await map_market(make_market(), (match,), resolver)

    assert result.status is MappingStatus.NO_MATCH
    assert result.reason == "event_context_conflict"


def test_link_decision_table():
    assert (
        evaluate_link_change(
            current_market_id=None, target_market_id="mkt_a", intent_exists=False
        )
        is LinkDecision.CREATE
    )
    assert (
        evaluate_link_change(
            current_market_id="mkt_a", target_market_id="mkt_a", intent_exists=False
        )
        is LinkDecision.NOOP
    )
    assert (
        evaluate_link_change(
            current_market_id="mkt_a", target_market_id="mkt_b", intent_exists=False
        )
        is LinkDecision.REPLACE
    )
    # Condition replacement after an intent is frozen; before it is allowed.
    assert (
        evaluate_link_change(
            current_market_id="mkt_a", target_market_id="mkt_b", intent_exists=True
        )
        is LinkDecision.FROZEN
    )
    assert (
        evaluate_link_change(
            current_market_id="mkt_a", target_market_id="mkt_a", intent_exists=True
        )
        is LinkDecision.NOOP
    )


def test_mapping_result_is_a_frozen_public_model():
    result = MappingResult(status=MappingStatus.NO_MATCH)
    assert result.match_id is None
    with pytest.raises(Exception):
        result.status = MappingStatus.MAPPED  # type: ignore[misc]
