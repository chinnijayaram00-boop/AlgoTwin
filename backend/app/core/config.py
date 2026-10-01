from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, derived from this file's location
# (`<root>/backend/app/core/config.py`) rather than from the process working
# directory. A relative `env_file` is resolved against the CWD, so launching
# uvicorn from anywhere other than the root silently skipped `.env` and every
# setting fell back to its default -- which is how the API ended up serving a
# CORS allowlist that rejected the real frontend origin. Anchoring the path to
# the repository makes configuration load identically from any directory.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPOSITORY_ROOT / ".env"

# The Vite dev server is pinned to 5174 (see frontend/vite.config.js), so this
# default must name that same origin. A stale default is worse than no default:
# it turns a missing `.env` into a CORS rejection, which the browser reports as
# an opaque "Failed to fetch" with nothing in the API access log.
#
# `localhost` and `127.0.0.1` are two spellings of one origin, but to CORS they
# are two different origins, and both address the same dev server. Allowing only
# the first means that whichever spelling the resolver happens to prefer decides
# whether the whole app works: a rejected preflight is answered with a bare 400
# and no `access-control-allow-origin`, which the browser surfaces as
# "Failed to fetch" without ever sending the real request. Listing both removes
# that dependency on name resolution order.
DEFAULT_CORS_ORIGINS = "http://localhost:5174,http://127.0.0.1:5174"


class Settings(BaseSettings):
    app_name: str = "ALgotwin API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./algotwin.db"
    auto_create_tables: bool = True
    # The catalog and the demo account are separate switches on purpose. The
    # catalog is the product: a deployment that sets `SEED_DEMO_DATA=false` to
    # stop shipping a published password must still get its problems, otherwise it
    # would serve an empty catalog and a judge with nothing to run.
    seed_problem_catalog: bool = True
    seed_demo_data: bool = True
    cors_origins: str = DEFAULT_CORS_ORIGINS
    ai_provider: str = "disabled"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_api_key: SecretStr | None = None
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1, le=10080)

    # Code execution. `EXECUTION_ENABLED=false` is the kill switch: it answers the
    # run endpoint with 503 and starts no worker process at all, which is what a
    # deployment wants if the host it runs on cannot offer the isolation a judge
    # needs. The two per-language switches exist because the answer to "can this
    # machine run Java" is host-specific, and a language that is switched off must
    # not be offered to the editor -- the same rule the catalog validator enforces.
    execution_enabled: bool = True
    execution_python: bool = True
    execution_javascript: bool = True
    # The total wall-clock one judge run may spend across all of its cases. Lower
    # than the 30s default for a single-process host; a deployment that wants
    # longer synchronous runs should move judging onto the background worker
    # rather than raise this.
    max_judge_wall_clock_ms: int = Field(default=30_000, ge=1_000, le=600_000)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
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
