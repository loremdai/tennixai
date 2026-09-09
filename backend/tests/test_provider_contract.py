from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain import (
    CapabilityStatus,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchSnapshot,
    MatchStatus,
    Player,
)
from app.errors import AppError
from app.identity import MemoryIdentityRepository
from app.providers.base import ProviderLiveEnvelope, TennisDataProvider
from app.providers.fake import FakeTennisProvider

NOW = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def provider() -> FakeTennisProvider:
    repository = MemoryIdentityRepository()
    return await FakeTennisProvider.create(
        identities=repository,
        now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_fake_provider_satisfies_contract_without_external_ids() -> None:
    repository = MemoryIdentityRepository()
    provider: TennisDataProvider = await FakeTennisProvider.create(
        identities=repository,
        now=lambda: NOW,
    )

    players = await provider.search_players("Sinner")
    fixtures = await provider.get_fixtures(player_id=players[0].id)
    live = await provider.get_live_matches(player_id=None)
    detail = await provider.get_match(fixtures[0].id)
    snapshot = await provider.get_match_snapshot(live[0].id)

    assert fixtures[0].status is MatchStatus.SCHEDULED
    assert detail.id == fixtures[0].id
    assert isinstance(snapshot, MatchSnapshot)
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


@pytest.mark.asyncio
async def test_get_player_returns_canonical_player_or_not_found(
    provider: FakeTennisProvider,
) -> None:
    players = await provider.search_players("sinner")
    player = await provider.get_player(players[0].id)

    assert isinstance(player, Player)
    assert player.id == players[0].id
    assert player.name == "Jannik Sinner"

    with pytest.raises(AppError) as error_info:
        await provider.get_player("ply_missing")
    assert error_info.value.code == "not_found"
    assert error_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_match_snapshot_is_version_consistent_and_honest_about_gaps(
    provider: FakeTennisProvider,
) -> None:
    live = await provider.get_live_matches()
    snapshot = await provider.get_match_snapshot(live[0].id)

    assert isinstance(snapshot, MatchSnapshot)
    assert snapshot.match.id == live[0].id
    assert snapshot.match.live_state is not None
    assert snapshot.state_version == snapshot.match.live_state.state_version
    assert snapshot.as_of.tzinfo is not None
    assert snapshot.points == ()
    assert snapshot.statistics == ()
    assert snapshot.momentum == ()
    # Missing P2 capabilities are declared, never fabricated as zero.
    declared = {item.capability: item.status for item in snapshot.quality}
    assert declared["point_by_point"] is CapabilityStatus.UNAVAILABLE
    assert declared["statistics"] is CapabilityStatus.UNAVAILABLE
    assert declared["momentum"] is CapabilityStatus.UNAVAILABLE

    fixtures = await provider.get_fixtures()
    upcoming_snapshot = await provider.get_match_snapshot(fixtures[0].id)
    assert upcoming_snapshot.state_version == 0

    with pytest.raises(AppError) as error_info:
        await provider.get_match_snapshot("mat_missing")
    assert error_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_get_recent_results_is_bounded_and_canonical(
    provider: FakeTennisProvider,
) -> None:
    players = await provider.search_players("sinner")

    results = await provider.get_recent_results(players[0].id, limit=5)
    again = await provider.get_recent_results(players[0].id, limit=5)
    assert results == []
    assert results is not again

    with pytest.raises(AppError) as error_info:
        await provider.get_recent_results("ply_missing", limit=5)
    assert error_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_get_head_to_head_returns_canonical_shape(
    provider: FakeTennisProvider,
) -> None:
    players = await provider.search_players("sinner")
    others = await provider.search_players("alcaraz")

    head_to_head = await provider.get_head_to_head(
        players[0].id, others[0].id, limit=5
    )

    assert isinstance(head_to_head, HeadToHead)
    assert head_to_head.first_player_id == players[0].id
    assert head_to_head.second_player_id == others[0].id
    assert head_to_head.meetings == ()
    assert head_to_head.freshness.provider == "fake"

    with pytest.raises(AppError) as error_info:
        await provider.get_head_to_head(players[0].id, "ply_missing", limit=5)
    assert error_info.value.code == "not_found"


def test_provider_live_envelope_is_private_typed_and_timezone_aware() -> None:
    envelope = ProviderLiveEnvelope(
        external_match_id="11997372",
        provider="api_tennis",
        channel="websocket",
        kind="snapshot",
        received_at=NOW,
        payload={"scores": {"1": {"1": "6"}}},
    )
    assert envelope.external_match_id == "11997372"
    assert envelope.kind == "snapshot"

    with pytest.raises(ValidationError):
        ProviderLiveEnvelope(
            external_match_id="1",
            provider="api_tennis",
            channel="websocket",
            kind="snapshot",
            received_at=datetime(2026, 9, 8, 10, 0),
            payload={},
        )

    with pytest.raises(ValidationError):
        ProviderLiveEnvelope(
            external_match_id="1",
            provider="api_tennis",
            channel="websocket",
            kind="snapshot",
            received_at=NOW,
            payload={},
            extra_field="x",
        )
