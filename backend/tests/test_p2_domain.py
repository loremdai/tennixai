"""P2 canonical domain models: enums, snapshot, point, statistic, momentum, quality."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain import (
    CapabilityStatus,
    CircuitTier,
    ConnectionStatus,
    DataFreshness,
    DataQuality,
    Discipline,
    Gender,
    HeadToHead,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    MatchStatus,
    MomentumObservation,
    Player,
    PointEvent,
    SetScore,
    StatisticName,
    StatisticProvenance,
    Tournament,
)

FIXED_NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def match() -> Match:
    return Match(
        id="mat_a",
        status=MatchStatus.LIVE,
        players=(
            Player(id="ply_a", name="Jannik Sinner"),
            Player(id="ply_b", name="Carlos Alcaraz"),
        ),
        tournament=Tournament(id="trn_a", name="ATP Finals"),
        scheduled_at=FIXED_NOW,
        live_state=LiveMatchState(),
        freshness=DataFreshness(provider="fake", observed_at=FIXED_NOW),
    )


def test_p2_enums_have_exact_frozen_values() -> None:
    assert [item.value for item in CircuitTier] == [
        "atp",
        "wta",
        "challenger",
        "itf",
        "other",
    ]
    assert [item.value for item in Gender] == ["men", "women", "mixed", "unknown"]
    assert [item.value for item in Discipline] == [
        "singles",
        "doubles",
        "team",
        "unknown",
    ]
    assert [item.value for item in ConnectionStatus] == [
        "connecting",
        "live",
        "reconnecting",
        "stale",
        "ended",
        "unavailable",
    ]
    assert [item.value for item in CapabilityStatus] == [
        "available",
        "partial",
        "unavailable",
        "stale",
    ]


def test_statistic_catalog_contains_exactly_the_22_approved_names() -> None:
    assert [item.value for item in StatisticName] == [
        "aces",
        "double_faults",
        "first_serve_percentage",
        "first_serve_points_won",
        "second_serve_points_won",
        "service_points_won",
        "service_games_won",
        "break_points_saved",
        "break_points_converted",
        "return_points_won",
        "first_return_points_won",
        "second_return_points_won",
        "return_games_won",
        "winners",
        "unforced_errors",
        "net_points_won",
        "total_points_won",
        "total_games_won",
        "match_points_saved",
        "average_first_serve_speed",
        "average_second_serve_speed",
        "distance_covered",
    ]
    assert len(StatisticName) == 22


def test_tournament_facets_default_to_honest_unknown_values() -> None:
    tournament = Tournament(id="trn_a", name="ATP Finals")

    assert tournament.circuit is CircuitTier.OTHER
    assert tournament.gender is Gender.UNKNOWN
    assert tournament.discipline is Discipline.UNKNOWN

    classified = Tournament(
        id="trn_b",
        name="WTA Finals",
        circuit="wta",
        gender="women",
        discipline="singles",
    )
    assert classified.circuit is CircuitTier.WTA
    assert classified.gender is Gender.WOMEN
    assert classified.discipline is Discipline.SINGLES


def test_live_match_state_gains_version_and_connection_defaults() -> None:
    state = LiveMatchState()
    assert state.state_version == 0
    assert state.connection_status is ConnectionStatus.UNAVAILABLE
    assert state.last_event_at is None
    assert state.as_of is None

    versioned = LiveMatchState(state_version=3, connection_status="live")
    assert versioned.state_version == 3
    assert versioned.connection_status is ConnectionStatus.LIVE

    with pytest.raises(ValidationError):
        LiveMatchState(state_version=-1)

    with pytest.raises(ValidationError):
        LiveMatchState(last_event_at=datetime(2026, 9, 9, 10, 0))


def test_match_snapshot_requires_matching_version(match: Match) -> None:
    versioned_match = match.model_copy(
        update={"live_state": LiveMatchState(state_version=3, connection_status="live")}
    )
    with pytest.raises(ValidationError):
        MatchSnapshot(
            match=versioned_match,
            points=(),
            statistics=(),
            momentum=(),
            quality=(),
            state_version=2,
            as_of=match.freshness.observed_at,
        )


def test_match_snapshot_accepts_matching_version_and_defaults(match: Match) -> None:
    versioned_match = match.model_copy(
        update={"live_state": LiveMatchState(state_version=3, connection_status="live")}
    )
    snapshot = MatchSnapshot(
        match=versioned_match, state_version=3, as_of=FIXED_NOW
    )

    assert snapshot.points == ()
    assert snapshot.statistics == ()
    assert snapshot.momentum == ()
    assert snapshot.quality == ()
    assert snapshot.state_version == 3
    assert snapshot.match.live_state is not None
    assert snapshot.match.live_state.state_version == 3


def test_match_snapshot_without_live_state_requires_version_zero(match: Match) -> None:
    scheduled = match.model_copy(update={"live_state": None})

    snapshot = MatchSnapshot(match=scheduled, state_version=0, as_of=FIXED_NOW)
    assert snapshot.state_version == 0

    with pytest.raises(ValidationError):
        MatchSnapshot(match=scheduled, state_version=1, as_of=FIXED_NOW)


def test_match_snapshot_rejects_naive_as_of_and_foreign_points(match: Match) -> None:
    with pytest.raises(ValidationError):
        MatchSnapshot(
            match=match, state_version=0, as_of=datetime(2026, 9, 9, 10, 0)
        )

    foreign_point = PointEvent(
        id="pe_other_1",
        match_id="mat_other",
        sequence=1,
        set_number=1,
        game_number=1,
        point_number=1,
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
        observed_at=FIXED_NOW,
        provider="fake",
        source_fingerprint="fp",
    )
    with pytest.raises(ValidationError):
        MatchSnapshot(
            match=match,
            points=(foreign_point,),
            state_version=0,
            as_of=FIXED_NOW,
        )


def test_point_event_bounds_and_required_fields() -> None:
    point = PointEvent(
        id="pe_1",
        match_id="mat_a",
        sequence=7,
        set_number=2,
        game_number=3,
        point_number=4,
        server_player_id="ply_a",
        winner_player_id=None,
        score_before=MatchScore(sets_won=(0, 1), sets=(), points=("30", "15")),
        score_after=MatchScore(sets_won=(0, 1), sets=(), points=("30", "30")),
        is_break_point=True,
        is_set_point=False,
        is_match_point=False,
        observed_at=FIXED_NOW,
        provider="fake",
        source_fingerprint="fp-7",
        revision=1,
        quality=DataQuality(
            capability="point_winner",
            status=CapabilityStatus.PARTIAL,
            provider="fake",
            reason="winner_indeterminate",
            observed_at=FIXED_NOW,
        ),
    )

    assert point.winner_player_id is None
    assert point.revision == 1
    assert point.quality is not None
    assert point.quality.status is CapabilityStatus.PARTIAL

    with pytest.raises(ValidationError):
        PointEvent(
            id="pe_2",
            match_id="mat_a",
            sequence=0,
            set_number=1,
            game_number=1,
            point_number=1,
            score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
            observed_at=FIXED_NOW,
            provider="fake",
            source_fingerprint="fp",
        )
    with pytest.raises(ValidationError):
        PointEvent(
            id="pe_3",
            match_id="mat_a",
            sequence=1,
            set_number=1,
            game_number=1,
            point_number=1,
            score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
            observed_at=FIXED_NOW,
            provider="fake",
            source_fingerprint="fp",
            revision=0,
        )
    with pytest.raises(ValidationError):
        PointEvent(
            id="pe_4",
            match_id="mat_a",
            sequence=1,
            set_number=1,
            game_number=1,
            point_number=1,
            score_after=MatchScore(sets_won=(0, 0), sets=(), points=("15", "0")),
            observed_at=datetime(2026, 9, 9, 10, 0),
            provider="fake",
            source_fingerprint="fp",
        )


def test_missing_statistic_is_not_zero() -> None:
    quality = DataQuality(
        capability="aces",
        status=CapabilityStatus.UNAVAILABLE,
        provider="fake",
        reason="not_reported",
        observed_at=FIXED_NOW,
    )
    assert quality.status is CapabilityStatus.UNAVAILABLE
    assert not hasattr(quality, "value")

    with pytest.raises(ValidationError):
        DataQuality(
            capability="aces",
            status=CapabilityStatus.UNAVAILABLE,
            provider="fake",
            observed_at=FIXED_NOW,
            value=0,
        )


def test_match_statistic_carries_both_players_and_availability() -> None:
    statistic = MatchStatistic(
        match_id="mat_a",
        name="aces",
        period="match",
        player1_value=8,
        player2_value=5,
        unit="count",
        provenance=StatisticProvenance.PROVIDER,
        availability=CapabilityStatus.AVAILABLE,
        as_of=FIXED_NOW,
    )
    assert statistic.name is StatisticName.ACES
    assert statistic.player1_value == 8
    assert statistic.player2_value == 5

    partial = MatchStatistic(
        match_id="mat_a",
        name=StatisticName.FIRST_SERVE_PERCENTAGE,
        period="set:1",
        player1_value=62.5,
        player2_value=None,
        unit="percent",
        availability=CapabilityStatus.PARTIAL,
        as_of=FIXED_NOW,
    )
    assert partial.player2_value is None

    derived = MatchStatistic(
        match_id="mat_a",
        name=StatisticName.TOTAL_POINTS_WON,
        availability=CapabilityStatus.AVAILABLE,
        provenance="derived_pbp",
        as_of=FIXED_NOW,
    )
    assert derived.provenance is StatisticProvenance.DERIVED_PBP
    assert derived.period == "match"

    with pytest.raises(ValidationError):
        MatchStatistic(
            match_id="mat_a",
            name="last_10_balls",
            availability=CapabilityStatus.AVAILABLE,
            as_of=FIXED_NOW,
        )


def test_momentum_observation_is_bounded_and_versioned() -> None:
    observation = MomentumObservation(
        match_id="mat_a",
        point_sequence=12,
        state_version=9,
        algorithm_version="recent_control_v1",
        value=37.5,
        leader_player_id="ply_a",
        is_provisional=False,
        as_of=FIXED_NOW,
        input_summary="12 determinate points; serve-adjusted residuals",
    )
    assert observation.value == 37.5
    assert observation.leader_player_id == "ply_a"

    provisional = MomentumObservation(
        match_id="mat_a",
        point_sequence=3,
        state_version=2,
        algorithm_version="recent_control_v1",
        value=-12.0,
        is_provisional=True,
        as_of=FIXED_NOW,
        input_summary="3 determinate points",
    )
    assert provisional.is_provisional is True
    assert provisional.leader_player_id is None

    for out_of_range in (-100.5, 100.5):
        with pytest.raises(ValidationError):
            MomentumObservation(
                match_id="mat_a",
                point_sequence=1,
                state_version=1,
                algorithm_version="recent_control_v1",
                value=out_of_range,
                as_of=FIXED_NOW,
                input_summary="x",
            )

    with pytest.raises(ValidationError):
        MomentumObservation(
            match_id="mat_a",
            point_sequence=1,
            state_version=1,
            algorithm_version="recent_control_v1",
            value=10.0,
            as_of=datetime(2026, 9, 9, 10, 0),
            input_summary="x",
        )


def test_head_to_head_defaults_to_empty_canonical_sets() -> None:
    head_to_head = HeadToHead(
        first_player_id="ply_a",
        second_player_id="ply_b",
        freshness=DataFreshness(provider="fake", observed_at=FIXED_NOW),
    )
    assert head_to_head.meetings == ()
    assert head_to_head.first_player_recent == ()
    assert head_to_head.second_player_recent == ()

    with pytest.raises(ValidationError):
        HeadToHead(
            first_player_id="ply_a",
            second_player_id="ply_b",
            freshness=DataFreshness(provider="fake", observed_at=FIXED_NOW),
            vendor_field="x",
        )


def test_p2_models_stay_frozen_and_forbid_extra_fields() -> None:
    quality = DataQuality(
        capability="aces",
        status=CapabilityStatus.AVAILABLE,
        provider="fake",
        observed_at=FIXED_NOW,
    )
    with pytest.raises(ValidationError):
        quality.status = CapabilityStatus.STALE  # type: ignore[misc]

    sets: tuple[SetScore, ...] = (SetScore(number=1, player1_games=6, player2_games=4),)
    assert sets[0].player1_games == 6
