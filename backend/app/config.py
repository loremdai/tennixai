from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TENNIX_", env_file=".env", extra="ignore")

    provider_mode: Literal["fake", "live"] = "fake"
    livetennis_api_key: SecretStr | None = None
    livetennis_base_url: str = "https://api.livetennisapi.com/api/public/v1"
    llm_mode: Literal["fake", "openai_compatible"] = "fake"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str = "qwen3.8-max-0902"
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    product_timezone: str = "Asia/Macau"
    cache_max_entries: int = 256
    fixed_now: str | None = None

    @model_validator(mode="after")
    def validate_required_credentials(self) -> "Settings":
        if self.provider_mode == "live" and (
            self.livetennis_api_key is None
            or not self.livetennis_api_key.get_secret_value().strip()
        ):
            raise ValueError("TENNIX_LIVETENNIS_API_KEY is required in live provider mode")
        if self.llm_mode == "openai_compatible" and (
            self.llm_api_key is None
            or not self.llm_api_key.get_secret_value().strip()
            or not self.llm_base_url
        ):
            raise ValueError("TENNIX_LLM_API_KEY and TENNIX_LLM_BASE_URL are required")
        return self
