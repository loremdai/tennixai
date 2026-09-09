from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TENNIX_", env_file=ROOT_ENV_FILE, extra="ignore"
    )

    provider_mode: Literal["fake", "live", "livetennis", "api_tennis"] = "fake"
    livetennis_api_key: SecretStr | None = None
    livetennis_base_url: str = "https://api.livetennisapi.com/api/public/v1"
    api_tennis_api_key: SecretStr | None = None
    api_tennis_base_url: str = "https://api.api-tennis.com/tennis/"
    api_tennis_ws_url: str = "wss://wss.api-tennis.com/live"
    api_tennis_ws_url: str = "wss://wss.api-tennis.com/live"
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
