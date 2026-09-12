"""Compact, topic-scoped facts for P2 Chat."""

import json
from datetime import UTC, datetime, timedelta

from app.chat.models import StructuredToolResult
from app.chat.orchestrator import _model_tool_result
from app.domain import (
    CapabilityStatus,
    DataFreshness,
    DataQuality,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    Player,
    PointEvent,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.intelligence import IntelligenceTopic, build_intelligence_packet

NOW = datetime(2026, 9, 10, 10, 0, tzinfo=UTC)


def point(sequence: int, *, winner: str | None = "ply_a", key: bool = False) -> PointEvent:
    return PointEvent(
        id=f"pe_{sequence}",
        match_id="mat_packet",
        sequence=sequence,
        set_number=1,
        game_number=1,
        point_number=sequence,
        server_player_id="ply_a",
        winner_player_id=winner,
        score_after=MatchScore(sets_won=(1, 0), sets=(), points=("30", "15")),
        is_break_point=key,
        observed_at=NOW + timedelta(seconds=sequence),
        provider="api_tennis",
        source_fingerprint=f"vendor-fingerprint-{sequence}",
    )


def snapshot() -> MatchSnapshot:
    match = Match(
        id="mat_packet",
        status="live",
        players=(
            Player(id="ply_a", name="Jannik Sinner"),
            Player(id="ply_b", name="Carlos Alcaraz"),
        ),
        tournament=Tournament(
            id="trn_packet",
            name="ATP Finals",
            circuit="atp",
            gender="men",
            discipline="singles",
        ),
        live_state=LiveMatchState(
            score=MatchScore(sets_won=(1, 0), sets=(), points=("30", "15")),
            server_player_id="ply_a",
            state_version=7,
        ),
        freshness=DataFreshness(provider="api_tennis", observed_at=NOW),
    )
    statistics = (
        MatchStatistic(
            match_id=match.id,
            name=StatisticName.ACES,
            player1_value=8,
            player2_value=5,
            provenance=StatisticProvenance.PROVIDER,
            availability=CapabilityStatus.AVAILABLE,
            as_of=NOW,
        ),
        MatchStatistic(
            match_id=match.id,
            name=StatisticName.FIRST_SERVE_PERCENTAGE,
            player1_value=68,
            player2_value=None,
            provenance=StatisticProvenance.PROVIDER,
            availability=CapabilityStatus.PARTIAL,
            as_of=NOW,
        ),
    )
    quality = (
        DataQuality(
            capability="statistics",
            status=CapabilityStatus.PARTIAL,
            provider="api_tennis",
            reason="one_player_missing",
            observed_at=NOW,
        ),
        DataQuality(
            capability="momentum",
            status=CapabilityStatus.UNAVAILABLE,
            provider="api_tennis",
            reason="not_reported",
            observed_at=NOW,
        ),
    )
    points = tuple(point(index, key=index == 25) for index in range(1, 26))
    momentum = tuple(
        {
            "match_id": match.id,
            "point_sequence": index,
            "state_version": 7,
            "algorithm_version": "recent-control-v1",
            "value": float(index),
            "leader_player_id": "ply_a",
            "is_provisional": index < 6,
            "as_of": NOW + timedelta(seconds=index),
            "input_summary": f"n={index};prior=0.6",
        }
        for index in range(1, 26)
    )
    return MatchSnapshot(
        match=match,
        points=points,
        statistics=statistics,
        momentum=momentum,
        quality=quality,
        state_version=7,
        as_of=NOW,
    )


def test_packet_is_bounded_versioned_and_vendor_safe() -> None:
    packet = build_intelligence_packet(snapshot(), topic=IntelligenceTopic.MOMENTUM)
    serialized = json.dumps(packet.model_dump(mode="json"), ensure_ascii=False)

    assert packet.match_id == "mat_packet"
    assert packet.state_version == 7
    assert packet.as_of == NOW
    assert len(packet.recent_points) == 20
    assert len(packet.momentum) == 20
    assert "event_key" not in serialized
    assert "api_tennis" not in serialized
    assert "vendor-fingerprint" not in serialized


def test_packet_selects_only_requested_topic_and_preserves_availability() -> None:
    packet = build_intelligence_packet(snapshot(), topic=IntelligenceTopic.STATISTICS)

    assert packet.statistics[0].availability is CapabilityStatus.AVAILABLE
    assert packet.statistics[1].availability is CapabilityStatus.PARTIAL
    assert packet.recent_points == ()
    assert packet.momentum == ()
    assert [(item.capability, item.status) for item in packet.quality] == [
        ("statistics", CapabilityStatus.PARTIAL),
        ("momentum", CapabilityStatus.UNAVAILABLE),
    ]


def test_packet_keeps_key_points_as_facts_separate_from_momentum() -> None:
    packet = build_intelligence_packet(snapshot(), topic=IntelligenceTopic.POINTS)

    assert [item.sequence for item in packet.recent_points] == list(range(6, 26))
    assert [item.sequence for item in packet.key_points] == [25]
    assert packet.momentum == ()


def test_packet_bounds_key_points_when_determinate_points_are_missing() -> None:
    source = snapshot()
    missing_winners = tuple(
        item.model_copy(update={"winner_player_id": None, "is_break_point": True})
        for item in source.points
    )
    bounded = source.model_copy(update={"points": missing_winners})

    packet = build_intelligence_packet(bounded, topic=IntelligenceTopic.POINTS)

    assert packet.recent_points == ()
    assert len(packet.key_points) == 20
    assert [item.sequence for item in packet.key_points] == list(range(6, 26))


def test_model_intelligence_result_labels_stat_values_with_player_names() -> None:
    packet = build_intelligence_packet(snapshot(), topic=IntelligenceTopic.STATISTICS)

    result = _model_tool_result(
        StructuredToolResult(kind="intelligence", packet=packet)
    )

    statistic = result["packet"]["statistics"][0]
    assert statistic["player_values"] == [
        {"player": "Jannik Sinner", "value": 8.0},
        {"player": "Carlos Alcaraz", "value": 5.0},
    ]
