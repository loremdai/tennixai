"""Live-local configuration validation and child environment construction.

Guards for the P4 local real runtime: only the dedicated loopback database
``tennix_live_local`` and Redis DB 11 are accepted, only ``api_tennis`` +
``paper`` modes, and only with the required credentials present. Errors carry
stable reason codes and never echo the supplied URL, host or any secret.
"""

from typing import Literal

from pydantic import SecretStr
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.config import Settings
from app.runtime.models import LiveLocalConfigurationError, LocalRuntimeSettings


LIVE_LOCAL_DATABASE_NAME = "tennix_live_local"
LIVE_LOCAL_REDIS_DATABASE = "11"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_CHILD_ROLES = frozenset({"runtime", "api", "verify"})


def require_live_local(settings: Settings) -> LocalRuntimeSettings:
    """Validate ``settings`` for live-local operation or raise a stable code."""
    if settings.provider_mode != "api_tennis":
        raise LiveLocalConfigurationError("LOCAL_PROVIDER_MODE_INVALID")
    if settings.p3_mode != "paper":
        raise LiveLocalConfigurationError("LOCAL_P3_MODE_INVALID")
    if (
        not _has_secret(settings.api_tennis_api_key)
        or not _has_secret(settings.llm_api_key)
        or not (settings.llm_base_url or "").strip()
    ):
        raise LiveLocalConfigurationError("LOCAL_CREDENTIALS_MISSING")
    _require_loopback_database(settings.local_runtime_database_url)
    _require_loopback_redis(settings.local_runtime_redis_url)
    return LocalRuntimeSettings(
        database_url=settings.local_runtime_database_url,
        redis_url=settings.local_runtime_redis_url,
        live_catalog_seconds=settings.local_runtime_live_catalog_seconds,
        upcoming_catalog_seconds=settings.local_runtime_upcoming_catalog_seconds,
        ranking_seconds=settings.local_runtime_ranking_seconds,
        market_discovery_seconds=settings.local_runtime_market_discovery_seconds,
        market_snapshot_seconds=settings.local_runtime_market_snapshot_seconds,
        market_snapshot_max_markets=settings.local_runtime_market_snapshot_max_markets,
        market_snapshot_token_batch_size=(
            settings.local_runtime_market_snapshot_token_batch_size
        ),
        market_quote_fresh_seconds=settings.local_runtime_market_quote_fresh_seconds,
    )


def child_environment(
    settings: Settings, *, role: Literal["runtime", "api", "verify"]
) -> dict[str, str]:
    """Return child-process environment overrides for a local runtime role.

    Pure function over validated settings: never mutates ``os.environ``, never
    writes any file, never emits ``NEXT_PUBLIC_*`` keys or credential values.
    """
    if role not in _CHILD_ROLES:
        raise LiveLocalConfigurationError("LOCAL_RUNTIME_ROLE_INVALID")
    live = require_live_local(settings)
    return {
        "TENNIX_DATABASE_URL": live.database_url,
        "TENNIX_REDIS_URL": live.redis_url,
        "TENNIX_PROVIDER_MODE": "api_tennis",
        "TENNIX_P3_MODE": "paper",
        "TENNIX_LOCAL_RUNTIME_ROLE": role,
    }


def _has_secret(secret: SecretStr | None) -> bool:
    return secret is not None and bool(secret.get_secret_value().strip())


def _parse_url(url: str, code: str) -> URL:
    try:
        return make_url(url)
    except ArgumentError:
        raise LiveLocalConfigurationError(code) from None


def _require_loopback_database(url: str) -> None:
    parsed = _parse_url(url, "LOCAL_DATABASE_NAME_INVALID")
    if (
        parsed.database != LIVE_LOCAL_DATABASE_NAME
        or (parsed.host or "").lower() not in _LOOPBACK_HOSTS
    ):
        raise LiveLocalConfigurationError("LOCAL_DATABASE_NAME_INVALID")


def _require_loopback_redis(url: str) -> None:
    parsed = _parse_url(url, "LOCAL_REDIS_DB_INVALID")
    if (
        parsed.database != LIVE_LOCAL_REDIS_DATABASE
        or (parsed.host or "").lower() not in _LOOPBACK_HOSTS
    ):
        raise LiveLocalConfigurationError("LOCAL_REDIS_DB_INVALID")
