"""Provider-final settlement interpreter tests (T64).

Settlement obeys only the Polymarket market's own final resolution and
rules: explicit 50–50 pays $0.50 per share, pending/disputed states never
settle locally, retirement/walkover/cancellation outcomes come from the
resolution payouts, and a tennis result alone can never settle a position
(the interpreter does not even accept one).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.markets.models import MarketResolution, ResolutionStatus
from app.paper.models import TrackName
from app.paper.settlement import SettlementBlocked, interpret_settlement

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def resolution(
    status: ResolutionStatus,
    *,
    payout_a: str | None = None,
    payout_b: str | None = None,
    market_id: str = "mkt_1",
) -> MarketResolution:
    payouts = ()
    confirmed = None
    if payout_a is not None and payout_b is not None:
        payouts = (
            {"player_id": "ply_a", "payout_per_share": Decimal(payout_a)},
            {"player_id": "ply_b", "payout_per_share": Decimal(payout_b)},
        )
        confirmed = NOW
    return MarketResolution(
        market_id=market_id,
        status=status,
        rules_version=1,
        payouts=payouts,
        confirmed_at=confirmed,
    )


def position(**overrides):
    params = {
        "match_id": "mat_1",
        "market_id": "mkt_1",
        "position_id": "pos_1",
        "outcome_player_id": "ply_a",
        "entry_cost": Decimal("10.00"),
        "shares": Decimal("20"),
        "exit_kind": "held",
    }
    params.update(overrides)
    return params


def test_provider_final_win_pays_full_and_loss_pays_nothing():
    won = interpret_settlement(
        position=position(),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="1", payout_b="0"),
        exit_proceeds=None,
        entry_fee=Decimal("0.05"),
        convergence_lock_price=None,
    )
    assert {result.track: result.net_pnl for result in won} == {
        TrackName.EV_EXIT: Decimal("9.95"),
        TrackName.HODL_BASELINE: Decimal("9.95"),
        TrackName.CONVERGENCE_LOCK: Decimal("9.95"),
    }

    lost = interpret_settlement(
        position=position(),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="0", payout_b="1"),
        exit_proceeds=None,
        entry_fee=Decimal("0.05"),
        convergence_lock_price=None,
    )
    assert all(result.net_pnl == Decimal("-10.05") for result in lost)


def test_explicit_fifty_fifty_pays_half_per_share():
    results = interpret_settlement(
        position=position(),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="0.5", payout_b="0.5"),
        exit_proceeds=None,
        entry_fee=Decimal("0.05"),
        convergence_lock_price=None,
    )

    hodl = next(r for r in results if r.track is TrackName.HODL_BASELINE)
    # 20 shares * $0.50 = $10 gross; net of the $0.05 entry fee.
    assert hodl.gross_payout == Decimal("10.00")
    assert hodl.payout_per_share == Decimal("0.5")
    assert hodl.net_pnl == Decimal("-0.05")


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (ResolutionStatus.PENDING, "RESOLUTION_PENDING"),
        (ResolutionStatus.PROPOSED, "RESOLUTION_PENDING"),
        (ResolutionStatus.DISPUTED, "RESOLUTION_DISPUTED"),
    ],
)
def test_non_final_states_never_settle_locally(status, reason):
    with pytest.raises(SettlementBlocked) as error:
        interpret_settlement(
            position=position(),
            resolution=resolution(status),
            exit_proceeds=None,
            entry_fee=Decimal("0.05"),
            convergence_lock_price=None,
        )
    assert error.value.reason_code == reason


def test_condition_replacement_does_not_migrate_old_positions():
    with pytest.raises(SettlementBlocked) as error:
        interpret_settlement(
            position=position(),
            resolution=resolution(
                ResolutionStatus.FINAL, payout_a="1", payout_b="0", market_id="mkt_NEW"
            ),
            exit_proceeds=None,
            entry_fee=Decimal("0.05"),
            convergence_lock_price=None,
        )
    assert error.value.reason_code == "MARKET_MISMATCH"


def test_ev_exit_track_uses_actual_exit_proceeds():
    results = interpret_settlement(
        position=position(exit_kind="sold"),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="0", payout_b="1"),
        exit_proceeds=Decimal("12.00"),
        entry_fee=Decimal("0.05"),
        exit_fee=Decimal("0.06"),
        convergence_lock_price=None,
    )

    by_track = {result.track: result for result in results}
    # EV track sold before the loss: +12.00 - 10.00 - fees.
    assert by_track[TrackName.EV_EXIT].net_pnl == Decimal("1.89")
    # HODL rode it to zero.
    assert by_track[TrackName.HODL_BASELINE].net_pnl == Decimal("-10.05")


def test_exit_missed_track_holds_to_settlement():
    results = interpret_settlement(
        position=position(exit_kind="exit_missed"),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="1", payout_b="0"),
        exit_proceeds=None,
        entry_fee=Decimal("0.05"),
        convergence_lock_price=None,
    )

    by_track = {result.track: result for result in results}
    assert by_track[TrackName.EV_EXIT].net_pnl == Decimal("9.95")


def test_convergence_lock_counterfactual_uses_recorded_lock_price():
    results = interpret_settlement(
        position=position(),
        resolution=resolution(ResolutionStatus.FINAL, payout_a="0", payout_b="1"),
        exit_proceeds=None,
        entry_fee=Decimal("0.05"),
        convergence_lock_price=Decimal("0.70"),
    )

    by_track = {result.track: result for result in results}
    lock = by_track[TrackName.CONVERGENCE_LOCK]
    # 20 shares locked at 0.70 = 14.00 gross before the market went to zero.
    assert lock.gross_payout == Decimal("14.00")
    assert lock.net_pnl == Decimal("3.95")
    # The main ledger tracks are untouched by the counterfactual.
    assert by_track[TrackName.HODL_BASELINE].net_pnl == Decimal("-10.05")


def test_interpreter_signature_accepts_no_tennis_result():
    import inspect

    parameters = set(inspect.signature(interpret_settlement).parameters)
    forbidden = {"winner", "match_winner", "winner_player_id", "tennis_result"}
    assert not (parameters & forbidden)
