"""Runtime health registry and decision freshness overlay (T78).

The registry is the single truthful source for fresh/degraded/stale/gap:

- An open, heartbeat-confirmed sports connection stays FRESH even while the
  score is quiet — silence in tennis is not staleness.
- A disconnect, queue overflow or reconciliation period produces a `gap`
  that revokes new BUY/SELL decisions until REST reconciliation succeeds.
- A low-frequency job failure produces `degraded` while preserving the
  prior canonical data path (last success timestamp and counts survive).

Only aggregate facts are stored and persisted: source state, timestamps,
sanitized stable reason codes, counts and paper/model status. Provider
identifiers, URLs, raw payloads and secrets never enter this module.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.runtime.models import (
    RuntimeHealth,
    RuntimeSourceHealth,
    RuntimeSourceStatus,
)

SPORTS_SOURCE = "tennis_live"
MARKET_SOURCE = "polymarket"
RECOVERY_REASON = "STARTUP_RECOVERY"
FALLBACK_REASON = "JOB_FAILED"

_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


def stable_reason_code(exc: BaseException) -> str:
    """Derive a sanitized stable reason code from an exception.

    Uses the exception's own `code` attribute when present (AppError),
    otherwise the class name. The result always matches
    ``^[A-Z][A-Z0-9_]*$``; messages, arguments and URLs are never used, so
    no provider identifier can leak through a reason code.
    """
    code = getattr(exc, "code", None)
    name = code if isinstance(code, str) and code else type(exc).__name__
    candidate = _NON_ALNUM.sub("_", _CAMEL_SPLIT.sub("_", name).upper()).strip("_")
    if not candidate or _REASON_CODE.fullmatch(candidate) is None:
        return FALLBACK_REASON
    return candidate


@dataclass(frozen=True)
class FreshnessOverlay:
    """What the DecisionWorker consumes before evaluating an action.

    Consumed structurally (``is_stale``/``has_gap``); the existing T63
    stale/gap hard gate applies the fail-closed semantics.
    """

    is_stale: bool = False
    has_gap: bool = False
    reason_code: str | None = None


@dataclass
class _SourceRecord:
    status: RuntimeSourceStatus = RuntimeSourceStatus.OK
    reason_code: str | None = None
    last_success_at: datetime | None = None
    last_event_at: datetime | None = None
    last_tracked: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class RuntimeHealthRegistry:
    """Per-source runtime health with a decision freshness overlay.

    ``stale_after`` optionally bounds how long a source may stay silent
    after its last confirmed success before it is reported stale; by default
    quietness alone never marks a healthy connection stale.
    """

    state: object
    clock: Callable[[], datetime]
    stale_after: Mapping[str, timedelta] | None = None
    paper_status: str = "paper_only"
    model_status: str = "not_promoted"
    _sources: dict[str, _SourceRecord] = field(default_factory=dict)
    _counter_sources: list[Callable[[], Mapping[str, int]]] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Marking
    # ------------------------------------------------------------------

    async def mark_success(self, source: str, *, tracked: int = 0) -> None:
        record = self._record(source)
        now = self.clock()
        record.status = RuntimeSourceStatus.OK
        record.reason_code = None
        record.last_success_at = now
        record.last_event_at = now
        record.success_count += 1
        if tracked:
            record.last_tracked = tracked

    async def mark_degraded(self, source: str, reason_code: str) -> None:
        self._require_reason_code(reason_code)
        record = self._record(source)
        # Degraded preserves the prior canonical data path: last success and
        # earlier counts are kept so `status` stays truthful without erasing
        # what the last healthy run produced.
        record.status = RuntimeSourceStatus.DEGRADED
        record.reason_code = reason_code
        record.last_event_at = self.clock()
        record.failure_count += 1

    async def mark_gap(self, source: str, reason_code: str) -> None:
        self._require_reason_code(reason_code)
        record = self._record(source)
        record.status = RuntimeSourceStatus.GAP
        record.reason_code = reason_code
        record.last_event_at = self.clock()
        record.failure_count += 1

    async def mark_recovered(self, source: str, *, tracked: int = 0) -> None:
        """Clear ONLY the explicit startup-recovery gap.

        A connection gap set while the daemon was down must survive until
        real reconciliation succeeds for that source; a blanket clear would
        hide it.
        """
        record = self._sources.get(source)
        if record is not None and record.reason_code == RECOVERY_REASON:
            await self.mark_success(source, tracked=tracked)

    @staticmethod
    def _require_reason_code(reason_code: str) -> None:
        if not isinstance(reason_code, str) or (
            _REASON_CODE.fullmatch(reason_code) is None
        ):
            raise ValueError("reason_code must be a sanitized stable code")

    def _record(self, source: str) -> _SourceRecord:
        return self._sources.setdefault(source, _SourceRecord())

    # ------------------------------------------------------------------
    # Freshness overlay
    # ------------------------------------------------------------------

    async def freshness_for(
        self, match_id: str, market_id: str | None
    ) -> FreshnessOverlay:
        considered = [SPORTS_SOURCE]
        if market_id is not None:
            considered.append(MARKET_SOURCE)
        has_gap = False
        is_stale = False
        reason: str | None = None
        now = self.clock()
        for source in considered:
            record = self._sources.get(source)
            if record is None:
                continue
            if record.status is RuntimeSourceStatus.GAP:
                has_gap = True
                reason = reason or record.reason_code
            bound = (self.stale_after or {}).get(source)
            if (
                bound is not None
                and record.last_success_at is not None
                and now - record.last_success_at > bound
            ):
                is_stale = True
                reason = reason or "STALE"
        return FreshnessOverlay(is_stale=is_stale, has_gap=has_gap, reason_code=reason)

    # ------------------------------------------------------------------
    # Aggregate persistence
    # ------------------------------------------------------------------

    def attach_counters(self, source: Callable[[], Mapping[str, int]]) -> None:
        """Register an aggregate counter source merged into `persist()`.

        Used to unify RealtimeWorker/MarketWorker callback failures and P3
        pipeline metrics into one health surface; values are counts only.
        """
        self._counter_sources.append(source)

    async def persist(self) -> RuntimeHealth:
        counters: dict[str, int] = {}
        for source in self._counter_sources:
            counters.update({str(key): int(value) for key, value in source().items()})
        health = RuntimeHealth(
            generated_at=self.clock(),
            sources={
                name: RuntimeSourceHealth(
                    status=record.status,
                    reason_code=record.reason_code,
                    last_success_at=record.last_success_at,
                    last_event_at=record.last_event_at,
                    last_tracked=record.last_tracked,
                    success_count=record.success_count,
                    failure_count=record.failure_count,
                )
                for name, record in self._sources.items()
            },
            counters=counters,
            paper_status=self.paper_status,
            model_status=self.model_status,
        )
        await self.state.save_health(health)  # type: ignore[attr-defined]
        return health
