"""Stable models for the P4 local real runtime configuration guards."""

from pydantic import Field

from app.domain import FrozenModel


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
