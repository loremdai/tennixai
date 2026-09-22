"""Stable models for the P4 local real runtime: configuration guards and the
canonical `runtime_state` payloads (init record, health summary)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.domain import FrozenModel


def _require_timezone(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value


class LiveLocalConfigurationError(ValueError):
    """Raised when live-local configuration is unsafe or incomplete.

    The error text is always exactly the stable reason code; it never
    contains the supplied URL, host, key or any other secret value.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LocalRuntimeSettings(FrozenModel):
    """Validated live-local runtime configuration handed to child roles."""

    database_url: str
    redis_url: str
    live_catalog_seconds: int = Field(ge=30, le=3_600)
    upcoming_catalog_seconds: int = Field(ge=300, le=86_400)
    ranking_seconds: int = Field(ge=3_600, le=604_800)
    market_discovery_seconds: int = Field(ge=60, le=3_600)
    market_snapshot_seconds: int = Field(default=120, ge=60, le=900)
    market_snapshot_max_markets: int = Field(default=250, ge=1, le=500)
    market_snapshot_token_batch_size: int = Field(default=100, ge=2, le=100)
    market_quote_fresh_seconds: int = Field(default=300, ge=120, le=1800)


class RuntimeInitRecord(FrozenModel):
    """Canonical record of one completed local runtime init.

    Stored as the `local_runtime_init` payload in `runtime_state`; aggregate
    counts only, never provider identifiers or raw provider data.
    """

    completed_at: datetime
    migration_revision: str
    player_count: int = Field(default=0, ge=0)
    match_count: int = Field(default=0, ge=0)

    @field_validator("completed_at")
    @classmethod
    def require_completed_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)  # type: ignore[return-value]


class RuntimeSourceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    GAP = "gap"


class RuntimeSourceHealth(FrozenModel):
    """Stable per-source health summary; reason codes only, never payloads."""

    status: RuntimeSourceStatus
    reason_code: str | None = None
    last_success_at: datetime | None = None
    last_event_at: datetime | None = None
    last_tracked: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)

    @field_validator("last_success_at", "last_event_at")
    @classmethod
    def require_success_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value)


class MarketQuoteCoverage(FrozenModel):
    """Aggregate coverage facts for the batch quote lane (T86).

    Counts and timestamps only: candidate/attempted markets, the display
    state buckets the pages would show, batch failures and the 429 backoff
    window. Provider identity, tokens, URLs and payloads never appear here.
    """

    generated_at: datetime
    candidate: int = Field(default=0, ge=0)
    attempted: int = Field(default=0, ge=0)
    fresh_realtime: int = Field(default=0, ge=0)
    fresh_snapshot: int = Field(default=0, ge=0)
    partial: int = Field(default=0, ge=0)
    no_liquidity: int = Field(default=0, ge=0)
    unavailable: int = Field(default=0, ge=0)
    stale: int = Field(default=0, ge=0)
    limited: int = Field(default=0, ge=0)
    batch_failures: int = Field(default=0, ge=0)
    rate_limited: bool = False
    retry_after_until: datetime | None = None
    last_successful_batch_at: datetime | None = None

    @field_validator("generated_at", "retry_after_until", "last_successful_batch_at")
    @classmethod
    def require_coverage_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value)


class RuntimeHealth(FrozenModel):
    """Aggregate runtime health summary written by the local runtime daemon.

    Stored as the `local_runtime_health` payload in `runtime_state`. Carries
    only aggregate facts — per-source status, stable reason codes, timestamps,
    counts, pipeline counters and paper/model status. Provider identifiers,
    URLs, raw payloads and secrets never appear here.
    """

    generated_at: datetime
    sources: dict[str, RuntimeSourceHealth] = Field(default_factory=dict)
    counters: dict[str, int] = Field(default_factory=dict)
    paper_status: str | None = None
    model_status: str | None = None
    market_coverage: MarketQuoteCoverage | None = None

    @field_validator("generated_at")
    @classmethod
    def require_generated_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)  # type: ignore[return-value]
