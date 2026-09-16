from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_default_environment_file_is_at_repository_root():
    assert Path(Settings.model_config["env_file"]) == REPOSITORY_ROOT / ".env"


def test_repository_has_one_environment_example():
    assert (REPOSITORY_ROOT / ".env.example").is_file()
    assert not (REPOSITORY_ROOT / "backend/.env.example").exists()
    assert not (REPOSITORY_ROOT / "frontend/.env.example").exists()


# ---------------------------------------------------------------------------
# P3 safe configuration (T57)
# ---------------------------------------------------------------------------


def test_p3_defaults_are_disabled_public_and_bounded():
    settings = Settings(_env_file=None)
    assert settings.p3_mode == "disabled"
    assert settings.p3_fixed_stake_usd == Decimal("10")
    assert settings.polymarket_gamma_base_url == "https://gamma-api.polymarket.com"
    assert settings.polymarket_clob_base_url == "https://clob.polymarket.com"
    assert settings.polymarket_ws_url == (
        "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    )
    assert settings.p3_model_artifact_dir == "artifacts/p3"
    assert settings.p3_max_market_subscriptions == 8
    assert settings.p3_market_book_freshness_seconds == 5
    assert settings.p3_decision_freshness_seconds == 15


def test_p3_mode_rejects_unknown_values():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_mode="trading")
    for mode in ("disabled", "shadow", "paper"):
        assert Settings(_env_file=None, p3_mode=mode).p3_mode == mode


def test_p3_numeric_bounds_are_enforced():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_max_market_subscriptions=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_max_market_subscriptions=101)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_market_book_freshness_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_market_book_freshness_seconds=61)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_decision_freshness_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_decision_freshness_seconds=121)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, p3_fixed_stake_usd=Decimal("0"))


def test_settings_never_expose_wallet_or_trading_credential_fields():
    forbidden_substrings = (
        "private_key",
        "wallet",
        "seed",
        "signature",
        "signer",
        "funder",
        "trading_key",
        "trading_credential",
        "trading_secret",
        "polymarket_api_key",
        "polymarket_secret",
    )
    for field_name in Settings.model_fields:
        lowered = field_name.lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in lowered, (
                f"setting {field_name} looks like a trading credential"
            )


def test_env_example_declares_public_p3_settings_without_credentials():
    text = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (
        "TENNIX_P3_MODE=disabled",
        "TENNIX_POLYMARKET_GAMMA_BASE_URL=https://gamma-api.polymarket.com",
        "TENNIX_POLYMARKET_CLOB_BASE_URL=https://clob.polymarket.com",
        "TENNIX_POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market",
        "TENNIX_P3_FIXED_STAKE_USD=10",
        "TENNIX_P3_MODEL_ARTIFACT_DIR=artifacts/p3",
        "TENNIX_P3_MAX_MARKET_SUBSCRIPTIONS=8",
        "TENNIX_P3_MARKET_BOOK_FRESHNESS_SECONDS=5",
        "TENNIX_P3_DECISION_FRESHNESS_SECONDS=15",
    ):
        assert key in text
    # Prohibitive comments may name forbidden concepts; actual config lines
    # must never define credential-like keys.
    config_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for line in config_lines:
        upper = line.upper()
        for forbidden in ("PRIVATE_KEY", "WALLET", "SEED_PHRASE", "TRADING_KEY"):
            assert forbidden not in upper, f"forbidden credential key line: {line}"
