from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class NormalizedEvent(BaseModel):
    external_id: str
    sport: Literal["football", "tennis_atp", "tennis_wta"]
    competition: str
    competition_key: str | None = None
    home_name: str
    away_name: str
    home_external_id: str | None = None
    away_external_id: str | None = None
    start_time: datetime
    status: str = "SCHEDULED"
    home_score: float | None = None
    away_score: float | None = None
    winner_name: str | None = None
    surface: str | None = None
    round: str | None = None
    source_timestamp: datetime
    source_updated_at: datetime | None = None
    raw_payload_hash: str | None = None


class NormalizedOdd(BaseModel):
    event_external_id: str
    bookmaker: str
    market: str
    selection: str
    decimal_odds: float = Field(gt=1.0, le=1000.0)
    point: float | None = None
    timestamp: datetime
    is_live: bool = False

    @field_validator("bookmaker", "market", "selection")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class ProviderBatch(BaseModel):
    events: list[NormalizedEvent]
    odds: list[NormalizedOdd]
    requests_remaining: int | None = None
    requests_used: int | None = None
    last_request_cost: int | None = None
    requested_sport_keys: list[str] = Field(default_factory=list)
    payload_hashes: list[str] = Field(default_factory=list)


class AvailableSport(BaseModel):
    key: str
    group: str
    title: str
    description: str | None = None
    active: bool = True
    has_outrights: bool = False


class OddsProvider(ABC):
    @abstractmethod
    async def get_available_sports(self) -> list[AvailableSport]: ...

    @abstractmethod
    async def get_events(self, sport_keys: list[str] | None = None) -> list[NormalizedEvent]: ...

    @abstractmethod
    async def get_odds(self, sport_key: str = "upcoming") -> ProviderBatch: ...

    @abstractmethod
    async def get_event_odds(self, sport_key: str, event_id: str) -> ProviderBatch: ...

    @abstractmethod
    async def get_historical_odds(
        self, sport_key: str, event_id: str, snapshot_at: datetime
    ) -> ProviderBatch: ...

    @abstractmethod
    async def get_markets(self) -> list[str]: ...


class FootballProvider(ABC):
    @abstractmethod
    async def get_fixtures(
        self, date_from: datetime, date_to: datetime
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_team_stats(
        self, team_external_id: str, competition_external_id: str, season: int
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_player_stats(self, player_external_id: str, season: int) -> dict[str, Any]: ...

    @abstractmethod
    async def get_standings(
        self, competition_external_id: str, season: int
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_fixture_statistics(self, event_external_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_injuries(self, event_external_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_suspensions(self, event_external_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_lineups(self, event_external_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_historical_matches(self, team_external_id: str) -> list[dict[str, Any]]: ...


class TennisProvider(ABC):
    @abstractmethod
    async def get_events(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_matches(self, date_from: datetime, date_to: datetime) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_rankings(self, tour: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_player_history(self, player_external_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_surface_stats(self, player_external_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_match_stats(self, event_external_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_tournament_info(self, tournament_external_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_players(self, player_external_id: str | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_h2h(
        self, first_player_external_id: str, second_player_external_id: str
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_odds(self, date_from: datetime, date_to: datetime) -> dict[str, Any]: ...
