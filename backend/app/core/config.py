from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Sports Value Engine"
    environment: str = "development"
    data_mode: Literal["real", "simulation"] = "real"
    enable_simulation: bool = False
    enable_mock_data: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./sports_value_engine.db"
    secret_key: str = "development-only-change-me"
    admin_api_token: str | None = None
    allowed_origins: str = "http://localhost:3001"
    app_timezone: str = "Europe/Berlin"
    the_odds_api_key: str | None = None
    odds_provider: Literal["the_odds_api"] = "the_odds_api"
    the_odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_regions: str = "eu"
    odds_markets: str = "h2h"
    odds_max_sports_per_sync: int = 24
    odds_quota_floor: int = 10
    football_provider: Literal["sportmonks", "api_football"] = "sportmonks"
    api_football_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"
    sportmonks_api_token: str | None = None
    tennis_provider: Literal["api_tennis"] = "api_tennis"
    api_tennis_key: str | None = None
    api_tennis_base_url: str = "https://api.api-tennis.com/tennis/"
    betfair_app_key: str | None = None

    min_odds: float = 1.45
    min_edge: float = 0.03
    min_ev: float = 0.03
    min_confidence: int = 70
    min_data_quality: int = 60
    odds_stale_minutes: int = 180
    odds_expired_minutes: int = 720
    provider_timeout_seconds: float = 15.0
    provider_detail_event_limit: int = 12
    scheduler_enabled: bool = True
    worker_schedules_enabled: bool = True
    odds_sync_interval_minutes: int = Field(default=30, ge=5, le=1440)
    deployment_version: str = "development"
    min_football_history_matches: int = Field(default=200, ge=30)
    min_tennis_history_matches: int = Field(default=300, ge=30)
    min_participant_history_matches: int = Field(default=10, ge=3)
    min_validation_samples: int = Field(default=200, ge=50)
    max_validation_brier: float = Field(default=0.24, gt=0, lt=1)
    max_validation_log_loss: float = Field(default=0.69, gt=0)
    max_validation_ece: float = Field(default=0.05, gt=0, lt=1)
    backfill_request_delay_seconds: float = Field(default=1.0, ge=0.1)

    @model_validator(mode="after")
    def validate_data_mode(self) -> "Settings":
        if self.database_url.startswith(("postgres://", "postgresql://")):
            self.database_url = "postgresql+asyncpg://" + self.database_url.split("://", 1)[1]
        if not self.database_url:
            self.database_url = "sqlite+aiosqlite:///./sports_value_engine.db"
        if self.environment.lower() == "production":
            if self.data_mode != "real":
                raise ValueError("Production requires DATA_MODE=real")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL DATABASE_URL")
        if (
            self.football_provider == "sportmonks"
            and not self.sportmonks_api_token
            and self.api_football_key
        ):
            self.football_provider = "api_football"
        if self.environment.lower() == "production" and self.enable_mock_data:
            raise ValueError("ENABLE_MOCK_DATA must be false in production")
        if self.data_mode == "simulation" and not self.enable_simulation:
            raise ValueError("DATA_MODE=simulation requires ENABLE_SIMULATION=true")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_real_mode(self) -> bool:
        return self.data_mode == "real"

    @property
    def football_provider_configured(self) -> bool:
        if self.football_provider == "api_football":
            return bool(self.api_football_key)
        return bool(self.sportmonks_api_token)

    @property
    def tennis_provider_configured(self) -> bool:
        return self.tennis_provider == "api_tennis" and bool(self.api_tennis_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
