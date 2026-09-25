from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ALgotwin API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./algotwin.db"
    auto_create_tables: bool = True
    seed_demo_data: bool = True
    cors_origins: str = "http://localhost:5173"
    ai_provider: str = "disabled"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_api_key: SecretStr | None = None
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=10080)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ai_is_configured(self) -> bool:
        return self.ai_provider.lower() != "disabled" and bool(self.ai_api_key and self.ai_api_key.get_secret_value())

    @property
    def jwt_secret(self) -> str:
        if self.jwt_secret_key is None:
            raise RuntimeError("JWT_SECRET_KEY must be configured before using authentication.")
        secret = self.jwt_secret_key.get_secret_value()
        if not secret.strip():
            raise RuntimeError("JWT_SECRET_KEY must not be empty.")
        return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
