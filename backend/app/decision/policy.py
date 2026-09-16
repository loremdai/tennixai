"""Versioned decision policy artifact (T63).

Read-only. A policy that cannot prove validation+shadow threshold selection
with a positive conservative net-EV lower bound is rejected, and a rejected
policy disables BUY/SELL entirely — the engine then only emits MARKET_ONLY
or NO BET with POLICY_DISABLED.
"""

import hashlib
import json
from pathlib import Path


class PolicyRejected(Exception):
    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code


class PolicyArtifact:
    def __init__(
        self,
        *,
        policy_version: str,
        buy_min_conservative_net_edge: float,
        buy_min_model_probability_gap: float,
        sell_min_exit_net_edge: float,
        net_ev_lower_bound: float,
        sha256: str,
    ) -> None:
        self.policy_version = policy_version
        self.buy_min_conservative_net_edge = buy_min_conservative_net_edge
        self.buy_min_model_probability_gap = buy_min_model_probability_gap
        self.sell_min_exit_net_edge = sell_min_exit_net_edge
        self.net_ev_lower_bound = net_ev_lower_bound
        self.sha256 = sha256

    @classmethod
    def load(
        cls, path: Path | str, *, expected_sha256: str | None = None
    ) -> "PolicyArtifact":
        path = Path(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise PolicyRejected(
                "POLICY_HASH_MISMATCH", "policy artifact hash does not match"
            )
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise PolicyRejected(
                "POLICY_UNREADABLE", "policy is not valid JSON"
            ) from exc

        selection = payload.get("threshold_selection") or {}
        if selection.get("dataset") != "validation":
            raise PolicyRejected(
                "THRESHOLD_SELECTED_ON_TEST",
                "decision thresholds must be selected on validation only",
            )
        if not selection.get("shadow_order_book_replay"):
            raise PolicyRejected(
                "MISSING_SHADOW_EVIDENCE",
                "thresholds require shadow order-book replay evidence",
            )
        evidence = payload.get("evidence") or {}
        if not evidence.get("validation") or not evidence.get("shadow"):
            raise PolicyRejected(
                "MISSING_VALIDATION_SHADOW_EVIDENCE",
                "policy requires both validation and shadow evidence",
            )
        try:
            net_ev_lower_bound = float(payload.get("net_ev_lower_bound"))
        except (TypeError, ValueError) as exc:
            raise PolicyRejected(
                "NON_POSITIVE_NET_EV_LOWER_BOUND",
                "conservative net-EV lower bound missing",
            ) from exc
        if net_ev_lower_bound <= 0:
            raise PolicyRejected(
                "NON_POSITIVE_NET_EV_LOWER_BOUND",
                "a non-positive conservative net-EV lower bound disables trading",
            )

        buy = payload.get("buy") or {}
        sell = payload.get("sell") or {}
        try:
            return cls(
                policy_version=str(payload.get("policy_version") or ""),
                buy_min_conservative_net_edge=float(
                    buy.get("min_conservative_net_edge")
                ),
                buy_min_model_probability_gap=float(
                    buy.get("min_model_probability_gap")
                ),
                sell_min_exit_net_edge=float(sell.get("min_exit_net_edge")),
                net_ev_lower_bound=net_ev_lower_bound,
                sha256=digest,
            )
        except (TypeError, ValueError) as exc:
            raise PolicyRejected(
                "POLICY_UNREADABLE", f"policy thresholds malformed: {exc}"
            ) from exc
