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


class RuntimeSourceHealth(FrozenModel):
    """Stable per-source health summary; reason codes only, never payloads."""

    status: RuntimeSourceStatus
    reason_code: str | None = None
    last_success_at: datetime | None = None
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)

    @field_validator("last_success_at")
    @classmethod
    def require_success_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone(value)


class RuntimeHealth(FrozenModel):
    """Minimal aggregate runtime health summary (extended by T78).

    Stored as the `local_runtime_health` payload in `runtime_state`.
    """

    generated_at: datetime
    sources: dict[str, RuntimeSourceHealth] = Field(default_factory=dict)

    @field_validator("generated_at")
    @classmethod
    def require_generated_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)  # type: ignore[return-value]
