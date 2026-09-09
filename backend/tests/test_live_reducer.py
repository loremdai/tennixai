"""Canonical live reducer: dedupe, append, correction, versioning."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain import (
    CapabilityStatus,
    DataFreshness,
    DataQuality,
    LiveMatchState,
    Match,
    MatchScore,
    MatchSnapshot,
    MatchStatistic,
    MatchStatus,
    Player,
    PointEvent,
    SetScore,
    StatisticName,
    StatisticProvenance,
    Tournament,
)
from app.momentum import ALGORITHM_VERSION
from app.realtime.models import ReductionChange
from app.realtime.reducer import reduce_live_snapshot

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
PLY_A = "ply_a"
PLY_B = "ply_b"


def base_match(status: MatchStatus = MatchStatus.LIVE) -> Match:
    return Match(
        id="mat_live",
        status=status,
        players=(
            Player(id=PLY_A, name="Player A"),
            Player(id=PLY_B, name="Player B"),
        ),
        tournament=Tournament(id="trn_t", name="Tulln"),
        scheduled_at=NOW - timedelta(hours=2),
        live_state=LiveMatchState(
            score=MatchScore(
                sets_won=(1, 1),
                sets=(
                    SetScore(number=1, player1_games=6, player2_games=4),
                    SetScore(number=2, player1_games=4, player2_games=6),
                    SetScore(number=3, player1_games=2, player2_games=2),
                ),
                points=("30", "15"),
            ),
            server_player_id=PLY_A,
            state_version=0,
        ),
        freshness=DataFreshness(provider="api_tennis", observed_at=NOW),
    )


def point(
    sequence: int,
    set_number: int,
    game_number: int,
    point_number: int,
    score_after: tuple[str, str],
    winner: str | None = PLY_A,
    fingerprint: str | None = None,
    revision: int = 1,
) -> PointEvent:
    return PointEvent(
        id=f"pe_mat_live_{set_number}_{game_number}_{point_number}",
        match_id="mat_live",
        sequence=sequence,
        set_number=set_number,
        game_number=game_number,
        point_number=point_number,
        server_player_id=PLY_A,
        winner_player_id=winner,
        score_after=MatchScore(sets_won=(0, 0), sets=(), points=score_after),
        observed_at=NOW,
        provider="api_tennis",
        source_fingerprint=fingerprint or f"fp-{set_number}-{game_number}-{point_number}",
        revision=revision,
    )


def statistic(name: StatisticName, p1: float, p2: float) -> MatchStatistic:
    return MatchStatistic(
        match_id="mat_live",
        name=name,
        period="match",
        player1_value=p1,
        player2_value=p2,
        unit="count",
        provenance=StatisticProvenance.PROVIDER,
        availability=CapabilityStatus.AVAILABLE,
        as_of=NOW,
    )


def supplier_snapshot(
    *,
    points: list[PointEvent] | None = None,
    statistics: list[MatchStatistic] | None = None,
    quality: list[DataQuality] | None = None,
    match: Match | None = None,
    as_of: datetime = NOW,
) -> MatchSnapshot:
    return MatchSnapshot(
        match=match or base_match(),
        points=tuple(points or []),
        statistics=tuple(statistics or []),
        momentum=(),
        quality=tuple(quality or []),
        state_version=0,
        as_of=as_of,
    )


def seven_point_history() -> list[PointEvent]:
    return [
        point(i, 3, 1, i, ("15", "0") if i % 2 else ("0", "15"))
        for i in range(1, 8)
    ]


def test_initial_reduction_assigns_version_one_and_reports_changes() -> None:
    candidate = supplier_snapshot(
        points=seven_point_history(), statistics=[statistic(StatisticName.ACES, 3, 1)]
    )

    reduction = reduce_live_snapshot(None, candidate)

    assert reduction.changed is True
    assert reduction.previous_version == 0
    assert reduction.snapshot.state_version == 1
    assert reduction.snapshot.match.live_state is not None
    assert reduction.snapshot.match.live_state.state_version == 1
    assert ReductionChange.SCORE_UPDATED in reduction.events
    assert ReductionChange.POINT_APPENDED in reduction.events
    assert ReductionChange.STATISTICS_UPDATED in reduction.events
    assert [p.sequence for p in reduction.snapshot.points] == list(range(1, 8))
    assert reduction.appended_points == reduction.snapshot.points
    assert reduction.point_revisions == ()
    assert reduction.recompute_from_sequence is None


def test_initial_reduction_computes_versioned_recent_control() -> None:
    reduction = reduce_live_snapshot(None, supplier_snapshot(points=seven_point_history()))

    assert len(reduction.snapshot.momentum) == 7
    assert all(
        observation.algorithm_version == ALGORITHM_VERSION
        and observation.state_version == reduction.snapshot.state_version
        for observation in reduction.snapshot.momentum
    )
    assert ReductionChange.MOMENTUM_UPDATED in reduction.events


def test_point_correction_recomputes_recent_control_from_changed_point() -> None:
    history = seven_point_history()
    first = reduce_live_snapshot(None, supplier_snapshot(points=history))
    corrected = history[3].model_copy(
        update={"winner_player_id": PLY_B, "source_fingerprint": "fp-corrected-4"}
    )

    reduction = reduce_live_snapshot(
        first.snapshot,
        supplier_snapshot(points=[*history[:3], corrected, *history[4:]]),
    )

    assert reduction.recompute_from_sequence == 4
    assert ReductionChange.MOMENTUM_UPDATED in reduction.events
    assert [item.value for item in reduction.snapshot.momentum[:3]] == pytest.approx(
        [item.value for item in first.snapshot.momentum[:3]]
    )
    assert reduction.snapshot.momentum[3].value != pytest.approx(
        first.snapshot.momentum[3].value
    )
    assert all(
        item.state_version == reduction.snapshot.state_version
        for item in reduction.snapshot.momentum[3:]
    )


def test_identical_supplier_snapshot_does_not_advance_version() -> None:
    first = reduce_live_snapshot(None, supplier_snapshot(points=seven_point_history()))
    repeated = reduce_live_snapshot(first.snapshot, supplier_snapshot(points=seven_point_history()))

    assert repeated.changed is False
    assert repeated.snapshot.state_version == first.snapshot.state_version
    assert repeated.events == ()
    assert repeated.appended_points == ()
    assert repeated.point_revisions == ()


def test_only_freshness_differences_are_not_state_changes() -> None:
    first = reduce_live_snapshot(None, supplier_snapshot(points=seven_point_history()))
    later = reduce_live_snapshot(
        first.snapshot,
        supplier_snapshot(points=seven_point_history(), as_of=NOW + timedelta(minutes=2)),
    )

    assert later.changed is False
    assert later.snapshot.state_version == first.snapshot.state_version


def test_appended_point_advances_version_and_keeps_sequences() -> None:
    history = seven_point_history()
    first = reduce_live_snapshot(None, supplier_snapshot(points=history))
    extended = [*history, point(8, 3, 2, 1, ("0", "15"), winner=PLY_B)]

    reduction = reduce_live_snapshot(
        first.snapshot, supplier_snapshot(points=extended)
    )

    assert reduction.changed is True
    assert reduction.snapshot.state_version == first.snapshot.state_version + 1
    assert ReductionChange.POINT_APPENDED in reduction.events
    assert [p.sequence for p in reduction.appended_points] == [8]
    assert [p.sequence for p in reduction.snapshot.points] == list(range(1, 9))
    assert reduction.point_revisions == ()
    assert reduction.recompute_from_sequence is None


def test_point_correction_starts_recompute_at_changed_sequence() -> None:
    history = seven_point_history()
    existing = reduce_live_snapshot(None, supplier_snapshot(points=history))

    corrected = [p.model_copy() for p in history]
    corrected[6] = corrected[6].model_copy(
        update={
            "winner_player_id": PLY_B,
            "source_fingerprint": "fp-corrected-7",
        }
    )

    reduction = reduce_live_snapshot(
        existing.snapshot, supplier_snapshot(points=corrected)
    )

    assert reduction.changed is True
    assert reduction.snapshot.state_version == existing.snapshot.state_version + 1
    assert ReductionChange.POINT_CORRECTED in reduction.events
    assert len(reduction.point_revisions) == 1
    assert reduction.point_revisions[0].sequence == 7
    assert reduction.point_revisions[0].before.winner_player_id == PLY_A
    assert reduction.point_revisions[0].after.winner_player_id == PLY_B
    assert reduction.recompute_from_sequence == 7
    # The stored point keeps its sequence and bumps its revision.
    stored = next(p for p in reduction.snapshot.points if p.sequence == 7)
    assert stored.revision == 2
    assert stored.winner_player_id == PLY_B


def test_statistics_only_change_emits_statistics_updated_and_keeps_points() -> None:
    history = seven_point_history()
    first = reduce_live_snapshot(
        None,
        supplier_snapshot(points=history, statistics=[statistic(StatisticName.ACES, 3, 1)]),
    )

    reduction = reduce_live_snapshot(
        first.snapshot,
        supplier_snapshot(points=history, statistics=[statistic(StatisticName.ACES, 4, 1)]),
    )

    assert reduction.changed is True
    assert reduction.events == (ReductionChange.STATISTICS_UPDATED,)
    assert reduction.appended_points == ()
    assert reduction.point_revisions == ()
    assert reduction.snapshot.points == first.snapshot.points
    aces = next(
        s for s in reduction.snapshot.statistics if s.name is StatisticName.ACES
    )
    assert aces.player1_value == 4


def test_terminal_status_advances_version_with_connection_updated() -> None:
    history = seven_point_history()
    first = reduce_live_snapshot(None, supplier_snapshot(points=history))

    finished_match = base_match(status=MatchStatus.FINISHED).model_copy(
        update={
            "winner_player_id": PLY_A,
            "live_state": LiveMatchState(
                score=MatchScore(
                    sets_won=(2, 1),
                    sets=(
                        SetScore(number=1, player1_games=6, player2_games=4),
                        SetScore(number=2, player1_games=4, player2_games=6),
                        SetScore(number=3, player1_games=7, player2_games=5),
                    ),
                    points=(None, None),
                ),
                server_player_id=None,
                state_version=0,
            ),
        }
    )

    reduction = reduce_live_snapshot(
        first.snapshot, supplier_snapshot(points=history, match=finished_match)
    )

    assert reduction.changed is True
    assert ReductionChange.SCORE_UPDATED in reduction.events
    assert ReductionChange.CONNECTION_UPDATED in reduction.events
    assert reduction.snapshot.match.status is MatchStatus.FINISHED
    assert reduction.snapshot.match.winner_player_id == PLY_A
    assert reduction.snapshot.state_version == first.snapshot.state_version + 1


def test_quality_change_emits_quality_updated() -> None:
    first = reduce_live_snapshot(None, supplier_snapshot(points=seven_point_history()))

    quality = [
        DataQuality(
            capability="statistics",
            status=CapabilityStatus.UNAVAILABLE,
            provider="api_tennis",
            reason="not_reported",
            observed_at=NOW,
        )
    ]
    reduction = reduce_live_snapshot(
        first.snapshot, supplier_snapshot(points=seven_point_history(), quality=quality)
    )

    assert reduction.changed is True
    assert reduction.events == (ReductionChange.QUALITY_UPDATED,)
    assert reduction.snapshot.quality == tuple(quality)


def test_dropped_tail_is_rebuilt_from_first_difference() -> None:
    history = seven_point_history()
    first = reduce_live_snapshot(None, supplier_snapshot(points=history))

    # Supplier drops point 5 and resends the rest: the tail is rebuilt.
    truncated = [p for i, p in enumerate(history) if i != 4]
    reduction = reduce_live_snapshot(
        first.snapshot, supplier_snapshot(points=truncated)
    )

    assert reduction.changed is True
    assert len(reduction.snapshot.points) == 6
    assert reduction.recompute_from_sequence == 5
    # Sequences stay contiguous after the rebuild.
    assert [p.sequence for p in reduction.snapshot.points] == list(range(1, 7))


def test_indeterminate_points_keep_quality_and_no_winner() -> None:
    unknown = point(1, 3, 1, 1, ("40", "40"), winner=None).model_copy(
        update={
            "quality": DataQuality(
                capability="point_winner",
                status=CapabilityStatus.PARTIAL,
                provider="api_tennis",
                reason="winner_indeterminate",
                observed_at=NOW,
            )
        }
    )
    reduction = reduce_live_snapshot(None, supplier_snapshot(points=[unknown]))

    stored = reduction.snapshot.points[0]
    assert stored.winner_player_id is None
    assert stored.quality is not None
    assert stored.quality.status is CapabilityStatus.PARTIAL


def test_reduction_snapshot_stays_version_consistent() -> None:
    first = reduce_live_snapshot(None, supplier_snapshot(points=seven_point_history()))
    with pytest.raises(Exception):
        # MatchSnapshot itself rejects version mismatches.
        first.snapshot.model_copy(update={"state_version": 99}).model_validate(
            first.snapshot.model_dump() | {"state_version": 99}
        )
