from pydantic import BaseModel, Field, model_validator


class SettingsUpdate(BaseModel):
    min_odds: float = Field(default=1.45, gt=1.0, le=20)
    min_edge: float = Field(default=0.03, ge=0, le=0.5)
    min_ev: float = Field(default=0.03, ge=0, le=2)
    min_confidence: int = Field(default=70, ge=0, le=100)
    timezone: str = Field(default="Europe/Berlin", min_length=1, max_length=80)
    odds_format: str = Field(default="DECIMAL", pattern="^(DECIMAL|AMERICAN|FRACTIONAL)$")
    sports_enabled: list[str] = Field(default_factory=lambda: ["football", "tennis"])
    notifications_enabled: bool = False
    auto_refresh_minutes: int = Field(default=15, ge=5, le=1440)


class ChallengeRequest(BaseModel):
    starting_bankroll: float = Field(default=10, gt=0, le=1_000_000)
    target_bankroll: float = Field(default=1000, gt=0, le=100_000_000)
    days: int = Field(default=7, ge=1, le=365)
    daily_opportunities: int = Field(default=2, ge=1, le=20)
    stake_fraction: float = Field(default=0.01, gt=0, le=0.1)
    win_probability: float = Field(default=0.56, gt=0, lt=1)
    average_odds: float = Field(default=1.9, gt=1, le=20)
    runs: int = Field(default=10_000, ge=1_000, le=100_000)

    @model_validator(mode="after")
    def target_exceeds_start(self) -> "ChallengeRequest":
        if self.target_bankroll <= self.starting_bankroll:
            raise ValueError("target bankroll must exceed starting bankroll")
        return self
