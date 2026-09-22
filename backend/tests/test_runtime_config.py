"""T73 live-local configuration and isolation guard tests.

Deterministic only: no network, no real services, no external quota.
"""

import os
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.runtime import (
    LiveLocalConfigurationError,
    LocalRuntimeSettings,
    child_environment,
    require_live_local,
)


VALID_DATABASE_URL = (
    "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix_live_local"
)
VALID_REDIS_URL = "redis://127.0.0.1:6379/11"


def local_settings(**overrides: Any) -> Settings:
    """Valid live-local settings; ``database_url``/``redis_url`` map to the
    dedicated ``local_runtime_*`` fields so tests read like the brief."""
    values: dict[str, Any] = {
        "provider_mode": "api_tennis",
        "api_tennis_api_key": "test-api-tennis-key",
        "llm_api_key": "test-llm-key",
        "llm_base_url": "https://llm.invalid/v1",
        "p3_mode": "paper",
    }
    if "database_url" in overrides:
        values["local_runtime_database_url"] = overrides.pop("database_url")
    if "redis_url" in overrides:
        values["local_runtime_redis_url"] = overrides.pop("redis_url")
    values.update(overrides)
    return Settings(_env_file=None, **values)


# ---------------------------------------------------------------------------
# Database isolation guards
# ---------------------------------------------------------------------------


def test_live_local_accepts_only_the_dedicated_loopback_database():
    settings = local_settings(
        database_url="postgresql+asyncpg://x:y@127.0.0.1:5432/tennix_live_local"
    )
    assert require_live_local(settings).database_url.endswith("/tennix_live_local")

    with pytest.raises(
        LiveLocalConfigurationError, match="LOCAL_DATABASE_NAME_INVALID"
    ):
        require_live_local(
            local_settings(
                database_url="postgresql+asyncpg://x:y@127.0.0.1:5432/tennix"
            )
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://x:y@localhost:5432/tennix_live_local",
        "postgresql+asyncpg://x:y@localhost/tennix_live_local",  # no explicit port
        "postgresql+asyncpg://x:y@[::1]:5432/tennix_live_local",  # IPv6 loopback
    ],
)
def test_live_local_accepts_loopback_host_variants(database_url: str):
    settings = local_settings(database_url=database_url)
    assert require_live_local(settings).database_url == database_url


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://x:y@127.0.0.1:5432/tennix",  # legacy database
        "postgresql+asyncpg://x:y@127.0.0.1:5432/tennix_test",  # test database
        "postgresql+asyncpg://x:y@127.0.0.1:5432/postgres",
        "postgresql+asyncpg://x:y@127.0.0.1:5432/tennix_live_local_extra",
        "postgresql+asyncpg://x:y@db.example.com:5432/tennix_live_local",
        "postgresql+asyncpg://x:y@10.0.0.5:5432/tennix_live_local",
        "postgresql+asyncpg://x:y@192.168.1.20:5432/tennix_live_local",
        "not-a-database-url",
    ],
)
def test_live_local_rejects_bad_database_names_and_hosts(database_url: str):
    settings = local_settings(database_url=database_url)
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_DATABASE_NAME_INVALID"


# ---------------------------------------------------------------------------
# Redis isolation guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "redis_url",
    [
        "redis://127.0.0.1:6379/11",
        "redis://localhost:6379/11",
        "redis://[::1]:6379/11",
    ],
)
def test_live_local_accepts_loopback_redis_db_eleven(redis_url: str):
    settings = local_settings(redis_url=redis_url)
    assert require_live_local(settings).redis_url == redis_url


@pytest.mark.parametrize(
    "redis_url",
    [
        "redis://127.0.0.1:6379/0",  # legacy cache DB
        "redis://127.0.0.1:6379/10",
        "redis://127.0.0.1:6379",  # no DB declared
        "redis://redis.example.com:6379/11",  # non-loopback host
        "not-a-redis-url",
    ],
)
def test_live_local_rejects_any_redis_other_than_loopback_db_eleven(redis_url: str):
    settings = local_settings(redis_url=redis_url)
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_REDIS_DB_INVALID"


# ---------------------------------------------------------------------------
# Mode and credential guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider_mode", ["fake", "live", "livetennis", "replay"])
def test_live_local_requires_api_tennis_provider_mode(provider_mode: str):
    overrides: dict[str, Any] = {"provider_mode": provider_mode}
    if provider_mode in ("live", "livetennis"):
        overrides["livetennis_api_key"] = "test-livetennis-key"
    settings = local_settings(**overrides)
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_PROVIDER_MODE_INVALID"


@pytest.mark.parametrize("p3_mode", ["disabled", "shadow"])
def test_live_local_requires_paper_p3_mode(p3_mode: str):
    settings = local_settings(p3_mode=p3_mode)
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_P3_MODE_INVALID"


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_api_key": None},
        {"llm_api_key": SecretStr("   ")},
        {"llm_base_url": None},
        {"llm_base_url": ""},
    ],
)
def test_live_local_requires_llm_credentials(overrides: dict[str, Any]):
    settings = local_settings(**overrides)
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_CREDENTIALS_MISSING"


def test_live_local_requires_api_tennis_credential_even_if_validator_bypassed():
    settings = local_settings()
    settings.api_tennis_api_key = None  # defense in depth behind Settings validator
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_CREDENTIALS_MISSING"

    settings = local_settings()
    settings.api_tennis_api_key = SecretStr("")
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    assert excinfo.value.code == "LOCAL_CREDENTIALS_MISSING"


# ---------------------------------------------------------------------------
# Interval bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "too_fast"),
    [
        ("local_runtime_live_catalog_seconds", 29),
        ("local_runtime_upcoming_catalog_seconds", 299),
        ("local_runtime_ranking_seconds", 3599),
        ("local_runtime_market_discovery_seconds", 59),
    ],
)
def test_settings_reject_too_fast_local_runtime_intervals(field: str, too_fast: int):
    with pytest.raises(ValidationError):
        local_settings(**{field: too_fast})


# ---------------------------------------------------------------------------
# Secret hygiene
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "postgresql+asyncpg://u:sup3r-s3cret@127.0.0.1:5432/tennix"},
        {
            "database_url": "postgresql+asyncpg://u:sup3r-s3cret@db.example.com/tennix_live_local"
        },
        {"redis_url": "redis://:sup3r-s3cret@127.0.0.1:6379/0"},
    ],
)
def test_error_text_contains_only_the_stable_reason_code(overrides: dict[str, Any]):
    settings = local_settings(
        api_tennis_api_key="super-secret-provider-key",
        llm_api_key="super-secret-llm-key",
        **overrides,
    )
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        require_live_local(settings)
    text = str(excinfo.value)
    assert text == excinfo.value.code
    for secret in (
        "sup3r-s3cret",
        "super-secret-provider-key",
        "super-secret-llm-key",
        "db.example.com",
        "postgresql",
        "redis://",
    ):
        assert secret not in text


# ---------------------------------------------------------------------------
# Child environment construction
# ---------------------------------------------------------------------------


def test_child_environment_never_exposes_credentials_to_frontend_keys():
    values = child_environment(local_settings(), role="runtime")
    assert values["TENNIX_LOCAL_RUNTIME_ROLE"] == "runtime"
    assert values["TENNIX_P3_MODE"] == "paper"
    assert not any(key.startswith("NEXT_PUBLIC_") for key in values)


@pytest.mark.parametrize("role", ["runtime", "api", "verify"])
def test_child_environment_overrides_for_each_role(role: str):
    settings = local_settings()
    values = child_environment(settings, role=role)
    assert values == {
        "TENNIX_DATABASE_URL": VALID_DATABASE_URL,
        "TENNIX_REDIS_URL": VALID_REDIS_URL,
        "TENNIX_PROVIDER_MODE": "api_tennis",
        "TENNIX_P3_MODE": "paper",
        "TENNIX_LOCAL_RUNTIME_ROLE": role,
    }
    # Credentials never travel through the override dict.
    assert "test-api-tennis-key" not in "".join(values.values())
    assert "test-llm-key" not in "".join(values.values())


def test_child_environment_uses_the_dedicated_local_runtime_urls():
    settings = local_settings(
        database_url="postgresql+asyncpg://x:y@localhost/tennix_live_local",
        redis_url="redis://localhost:6379/11",
    )
    values = child_environment(settings, role="api")
    assert values["TENNIX_DATABASE_URL"] == (
        "postgresql+asyncpg://x:y@localhost/tennix_live_local"
    )
    assert values["TENNIX_REDIS_URL"] == "redis://localhost:6379/11"


@pytest.mark.parametrize("role", ["RUNTIME", "Runtime", "off", "launcher", ""])
def test_child_environment_rejects_invalid_roles(role: str):
    settings = local_settings()
    with pytest.raises(LiveLocalConfigurationError) as excinfo:
        child_environment(settings, role=role)
    assert excinfo.value.code == "LOCAL_RUNTIME_ROLE_INVALID"


def test_child_environment_validates_live_local_configuration_first():
    settings = local_settings(
        database_url="postgresql+asyncpg://x:y@127.0.0.1:5432/tennix"
    )
    with pytest.raises(
        LiveLocalConfigurationError, match="LOCAL_DATABASE_NAME_INVALID"
    ):
        child_environment(settings, role="runtime")


def test_child_environment_never_mutates_os_environ():
    before = dict(os.environ)
    child_environment(local_settings(), role="runtime")
    assert dict(os.environ) == before

    before = dict(os.environ)
    with pytest.raises(LiveLocalConfigurationError):
        child_environment(local_settings(p3_mode="shadow"), role="verify")
    assert dict(os.environ) == before


def test_unknown_extra_environment_keys_are_ignored(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TENNIX_LOCAL_RUNTIME_UNRELATED", "whatever")
    settings = local_settings()
    assert require_live_local(settings).database_url == VALID_DATABASE_URL
    assert (
        child_environment(settings, role="verify")["TENNIX_LOCAL_RUNTIME_ROLE"]
        == "verify"
    )


# ---------------------------------------------------------------------------
# Model shape
# ---------------------------------------------------------------------------


def test_local_runtime_settings_are_frozen():
    live = require_live_local(local_settings())
    assert isinstance(live, LocalRuntimeSettings)
    assert live.live_catalog_seconds == 60
    assert live.upcoming_catalog_seconds == 600
    assert live.ranking_seconds == 86400
    assert live.market_discovery_seconds == 120
    with pytest.raises(ValidationError):
        live.database_url = "postgresql+asyncpg://x:y@127.0.0.1:5432/tennix"


def test_live_local_configuration_error_is_a_value_error():
    error = LiveLocalConfigurationError("LOCAL_DATABASE_NAME_INVALID")
    assert isinstance(error, ValueError)
    assert error.code == "LOCAL_DATABASE_NAME_INVALID"
    assert str(error) == "LOCAL_DATABASE_NAME_INVALID"


def test_live_local_settings_carry_the_bounded_snapshot_configuration():
    settings = local_settings(
        local_runtime_market_snapshot_seconds=300,
        local_runtime_market_snapshot_max_markets=120,
        local_runtime_market_snapshot_token_batch_size=40,
        local_runtime_market_quote_fresh_seconds=600,
    )
    live = require_live_local(settings)
    assert live.market_snapshot_seconds == 300
    assert live.market_snapshot_max_markets == 120
    assert live.market_snapshot_token_batch_size == 40
    assert live.market_quote_fresh_seconds == 600

    defaults = require_live_local(local_settings())
    assert defaults.market_snapshot_seconds == 120
    assert defaults.market_snapshot_max_markets == 250
    assert defaults.market_snapshot_token_batch_size == 100
    assert defaults.market_quote_fresh_seconds == 300
