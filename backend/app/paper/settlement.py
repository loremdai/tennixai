"""Provider-final settlement interpreter (T64).

Settlement obeys only the market's own final resolution and frozen rules.
Pending/proposed/disputed states never settle locally; a tennis result is
not even an accepted input. Explicit 50–50 resolutions pay $0.50 per
share; condition replacement never migrates an old position. All three
evaluation tracks are produced from the single entry without creating
extra positions.
"""

from collections.abc import Mapping
from decimal import Decimal

from app.markets.models import MarketResolution, ResolutionStatus
from app.paper.models import PaperTrackResult, TrackExitKind, TrackName


class SettlementBlocked(Exception):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


def interpret_settlement(
    *,
    position: Mapping,
    resolution: MarketResolution,
    exit_proceeds: Decimal | None,
    entry_fee: Decimal,
    exit_fee: Decimal = Decimal("0"),
    convergence_lock_price: Decimal | None = None,
) -> tuple[PaperTrackResult, ...]:
    """Compute the three track results for one settled position.

    `position` carries: match_id, market_id, position_id,
    outcome_player_id, entry_cost, shares and exit_kind
    ("sold" | "exit_missed" | "held").
    """
    if resolution.status is not ResolutionStatus.FINAL:
        reason = (
            "RESOLUTION_DISPUTED"
            if resolution.status is ResolutionStatus.DISPUTED
            else "RESOLUTION_PENDING"
        )
        raise SettlementBlocked(reason, "only provider-final resolution settles")
    if resolution.market_id != position["market_id"]:
        raise SettlementBlocked(
            "MARKET_MISMATCH",
            "condition replacement never migrates an existing position",
        )

    outcome_player_id = position["outcome_player_id"]
    payout_per_share = next(
        (
            payout.payout_per_share
            for payout in resolution.payouts
            if payout.player_id == outcome_player_id
        ),
        None,
    )
    if payout_per_share is None:
        raise SettlementBlocked(
            "PAYOUT_MISSING", "final resolution lacks the held outcome payout"
        )

    shares = Decimal(str(position["shares"]))
    entry_cost = Decimal(str(position["entry_cost"]))
    settlement_payout = (shares * payout_per_share).quantize(Decimal("0.000001"))
    exit_kind = str(position.get("exit_kind", "held"))
    settled_at = resolution.confirmed_at

    # --- EV_EXIT main track ---
    if exit_kind == "sold" and exit_proceeds is not None:
        ev_kind = TrackExitKind.SOLD
        ev_gross = Decimal(str(exit_proceeds))
        ev_exit_price = (ev_gross / shares).quantize(Decimal("0.000001"))
        ev_net = ev_gross - entry_cost - entry_fee - exit_fee
    elif exit_kind == "exit_missed":
        ev_kind = TrackExitKind.EXIT_MISSED
        ev_gross = settlement_payout
        ev_exit_price = None
        ev_net = ev_gross - entry_cost - entry_fee
    else:
        ev_kind = TrackExitKind.HELD_TO_SETTLEMENT
        ev_gross = settlement_payout
        ev_exit_price = None
        ev_net = ev_gross - entry_cost - entry_fee

    # --- HODL baseline counterfactual ---
    hodl_net = settlement_payout - entry_cost - entry_fee

    # --- Convergence-lock counterfactual ---
    if convergence_lock_price is not None:
        lock_kind = TrackExitKind.CONVERGENCE_LOCKED
        lock_gross = (shares * Decimal(str(convergence_lock_price))).quantize(
            Decimal("0.000001")
        )
        lock_exit_price = Decimal(str(convergence_lock_price))
    else:
        lock_kind = TrackExitKind.HELD_TO_SETTLEMENT
        lock_gross = settlement_payout
        lock_exit_price = None
    lock_net = lock_gross - entry_cost - entry_fee

    common = {
        "match_id": position["match_id"],
        "position_id": position["position_id"],
        "shares": shares,
        "payout_per_share": payout_per_share,
        "settled_at": settled_at,
    }
    return (
        PaperTrackResult(
            **common,
            track=TrackName.EV_EXIT,
            exit_kind=ev_kind,
            exit_average_price=ev_exit_price,
            gross_payout=ev_gross,
            net_pnl=ev_net,
        ),
        PaperTrackResult(
            **common,
            track=TrackName.HODL_BASELINE,
            exit_kind=TrackExitKind.HELD,
            gross_payout=settlement_payout,
            net_pnl=hodl_net,
        ),
        PaperTrackResult(
            **common,
            track=TrackName.CONVERGENCE_LOCK,
            exit_kind=lock_kind,
            exit_average_price=lock_exit_price,
            gross_payout=lock_gross,
            net_pnl=lock_net,
        ),
    )
