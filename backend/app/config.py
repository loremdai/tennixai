from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TENNIX_", env_file=ROOT_ENV_FILE, extra="ignore"
    )

    provider_mode: Literal["fake", "live", "livetennis", "api_tennis", "replay"] = "fake"
    livetennis_api_key: SecretStr | None = None
    livetennis_base_url: str = "https://api.livetennisapi.com/api/public/v1"
    api_tennis_api_key: SecretStr | None = None
    api_tennis_base_url: str = "https://api.api-tennis.com/tennis/"
    api_tennis_ws_url: str = "wss://wss.api-tennis.com/live"
    replay_fixture_path: str = "tests/fixtures/replay/live_match.jsonl"
    replay_speed: float = Field(default=20.0, gt=0, le=10_000)
    replay_identity_namespace: str = "replay"
    llm_mode: Literal["fake", "openai_compatible"] = "fake"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str = "qwen3.8-max-0902"
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    product_timezone: str = "Asia/Macau"
    cache_max_entries: int = 256
    fixed_now: str | None = None
    database_url: str = "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix"
    redis_url: str = "redis://127.0.0.1:6379/0"
    raw_payload_retention_days: int = Field(default=14, ge=1, le=90)
    max_live_subscriptions: int = Field(default=8, ge=1, le=100)
    viewer_lease_seconds: int = Field(default=45, ge=30, le=120)
    subscription_grace_seconds: int = Field(default=60, ge=0, le=300)
    sse_heartbeat_seconds: int = Field(default=15, ge=1, le=60)
    # P3 read-only market intelligence and paper trading. Public Polymarket
    # endpoints only; no wallet, private key, signing or trading credential
    # setting may ever be added here.
    p3_mode: Literal["disabled", "shadow", "paper"] = "disabled"
    p3_fixed_stake_usd: Decimal = Field(
        default=Decimal("10"), gt=Decimal("0"), le=Decimal("1000")
    )
    polymarket_gamma_base_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_base_url: str = "https://clob.polymarket.com"
    polymarket_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    p3_model_artifact_dir: str = "artifacts/p3"
    p3_max_market_subscriptions: int = Field(default=8, ge=1, le=100)
    p3_market_book_freshness_seconds: int = Field(default=5, ge=1, le=60)
    p3_decision_freshness_seconds: int = Field(default=15, ge=1, le=120)
    p3_tracking_window_minutes: int = Field(default=120, ge=5, le=2880)
    # P4 local real runtime. Live-local runs are isolated on the dedicated
    # loopback database tennix_live_local and Redis DB 11; the guards live in
    # app/runtime/config.py and never accept shared or production hosts.
    local_runtime_role: Literal["off", "api", "runtime", "verify"] = "off"
    local_runtime_database_url: str = (
        "postgresql+asyncpg://tennix:tennix@127.0.0.1:5432/tennix_live_local"
    )
    local_runtime_redis_url: str = "redis://127.0.0.1:6379/11"
    local_runtime_live_catalog_seconds: int = Field(default=60, ge=30, le=3600)
    local_runtime_upcoming_catalog_seconds: int = Field(default=600, ge=300, le=86400)
    local_runtime_ranking_seconds: int = Field(default=86400, ge=3600, le=604800)
    local_runtime_market_discovery_seconds: int = Field(default=120, ge=60, le=3600)
    # P4.3 coverage lane: bounded public batch quote snapshots. The lane only
    # fills display quotes; it never subscribes a WebSocket, calls the LLM or
    # touches prediction/decision/paper.
    local_runtime_market_snapshot_seconds: int = Field(default=120, ge=60, le=900)
    local_runtime_market_snapshot_max_markets: int = Field(default=250, ge=1, le=500)
    local_runtime_market_snapshot_token_batch_size: int = Field(
        default=100, ge=2, le=100
    )
    local_runtime_market_quote_fresh_seconds: int = Field(default=300, ge=120, le=1800)

    @model_validator(mode="after")
    def validate_required_credentials(self) -> "Settings":
        if self.provider_mode in ("live", "livetennis") and (
            self.livetennis_api_key is None
            or not self.livetennis_api_key.get_secret_value().strip()
        ):
            raise ValueError("TENNIX_LIVETENNIS_API_KEY is required in live provider mode")
        if self.provider_mode == "api_tennis" and (
            self.api_tennis_api_key is None
            or not self.api_tennis_api_key.get_secret_value().strip()
        ):
            raise ValueError(
                "TENNIX_API_TENNIS_API_KEY is required in api_tennis provider mode"
            )
        if self.llm_mode == "openai_compatible" and (
            self.llm_api_key is None
            or not self.llm_api_key.get_secret_value().strip()
            or not self.llm_base_url
        ):
            raise ValueError("TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL are required")
        return self
