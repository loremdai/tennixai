from datetime import datetime, timezone

import pytest

from app.domain import LiveMatchState, Match, MatchStatus, Player
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.base import TennisDataProvider
from app.providers.fake import FakeTennisProvider


@pytest.fixture()
def provider() -> TennisDataProvider:
    repository = MemoryIdentityRepository()
    return FakeTennisProvider(
        identities=repository,
        now=lambda: datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_fake_provider_satisfies_contract_without_external_ids() -> None:
    repository = MemoryIdentityRepository()
    provider: TennisDataProvider = FakeTennisProvider(
        identities=repository,
        now=lambda: datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
    )

    players = await provider.search_players("Sinner")
    fixtures = await provider.get_fixtures(player_id=players[0].id)
    live = await provider.get_live_matches(player_id=None)
    detail = await provider.get_match(fixtures[0].id)
    score = await provider.get_score(live[0].id)

    assert fixtures[0].status is MatchStatus.SCHEDULED
    assert detail.id == fixtures[0].id
    assert score.server_player_id == live[0].players[0].id
    assert all("fake-" not in item.id for item in [*players, *fixtures, *live])


@pytest.mark.asyncio
async def test_search_players_is_case_insensitive_substring(provider: TennisDataProvider) -> None:
    exact = await provider.search_players("Jannik Sinner")
    partial = await provider.search_players("sinner")

    assert len(exact) == 1
    assert exact[0].name == "Jannik Sinner"
    assert [player.id for player in partial] == [player.id for player in exact]

    missing = await provider.search_players("Federer")
    assert missing == []


@pytest.mark.asyncio
async def test_fixtures_contain_scheduled_match_with_full_metadata(
    provider: TennisDataProvider,
) -> None:
    fixtures = await provider.get_fixtures()

    assert len(fixtures) == 1
    match = fixtures[0]
    assert match.status is MatchStatus.SCHEDULED
    assert match.scheduled_at == datetime(2026, 9, 8, 12, 30, tzinfo=timezone.utc)
    assert match.round == "Semifinal"
    assert match.surface == "hard"
    assert match.indoor is True
    assert match.format == "BO3"
    assert match.live_state is None
    assert [player.name for player in match.players] == ["Jannik Sinner", "Carlos Alcaraz"]


@pytest.mark.asyncio
async def test_live_match_carries_score_and_server(provider: TennisDataProvider) -> None:
    live = await provider.get_live_matches()

    assert len(live) == 1
    match = live[0]
    assert match.status is MatchStatus.LIVE
    assert match.scheduled_at == datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    assert match.live_state is not None
    score = match.live_state.score
    assert score is not None
    assert score.sets_won == (1, 1)
    assert [(row.player1_games, row.player2_games) for row in score.sets] == [
        (6, 4),
        (4, 6),
        (4, 5),
    ]
    assert score.points == ("30", "15")
    assert match.live_state.server_player_id == match.players[0].id


@pytest.mark.asyncio
async def test_list_methods_filter_by_player_id(provider: TennisDataProvider) -> None:
    players = await provider.search_players("djokovic")
    djokovic = players[0]

    live_filtered = await provider.get_live_matches(player_id=djokovic.id)
    assert live_filtered == []

    fixtures_filtered = await provider.get_fixtures(player_id=djokovic.id)
    assert fixtures_filtered == []

    sinner = (await provider.search_players("sinner"))[0]
    assert len(await provider.get_live_matches(player_id=sinner.id)) == 1
    assert len(await provider.get_fixtures(player_id=sinner.id)) == 1


@pytest.mark.asyncio
async def test_get_score_returns_live_state(provider: TennisDataProvider) -> None:
    live = await provider.get_live_matches()
    state = await provider.get_score(live[0].id)

    assert isinstance(state, LiveMatchState)
    assert state.score is not None
    assert state.server_player_id == live[0].players[0].id


@pytest.mark.asyncio
async def test_unknown_ids_raise_not_found(provider: TennisDataProvider) -> None:
    with pytest.raises(AppError) as match_error:
        await provider.get_match("mat_missing")
    assert match_error.value.code == "not_found"
    assert match_error.value.status_code == 404

    with pytest.raises(AppError) as score_error:
        await provider.get_score("mat_missing")
    assert score_error.value.code == "not_found"
    assert score_error.value.status_code == 404


@pytest.mark.asyncio
async def test_public_methods_return_new_lists(provider: TennisDataProvider) -> None:
    first = await provider.get_live_matches()
    second = await provider.get_live_matches()

    assert first is not second
    assert first == second
    assert isinstance(first[0], Match)
    assert isinstance(first[0].players[0], Player)
