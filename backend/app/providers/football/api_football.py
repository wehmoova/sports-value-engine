import asyncio
from datetime import datetime
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import FootballProvider
from app.providers.odds.the_odds_api import ProviderError, payload_hash


class ApiFootballProvider(FootballProvider):
    """API-Football v3 adapter. All methods return validated provider records."""

    def __init__(self, settings: Settings) -> None:
        if not settings.api_football_key:
            raise ValueError("API_FOOTBALL_KEY is not configured")
        self._api_key = settings.api_football_key
        self._base_url = settings.api_football_base_url.rstrip("/")
        self._timeout = settings.provider_timeout_seconds
        self.last_latency_ms: float | None = None
        self.last_status_code: int | None = None
        self.rate_limit_remaining: int | None = None
        self.last_payload_hash: str | None = None

    async def _request(
        self, endpoint: str, params: dict[str, str]
    ) -> list[dict[str, Any]] | dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            started = perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        f"{self._base_url}/{endpoint.lstrip('/')}",
                        params=params,
                        headers={"x-apisports-key": self._api_key},
                    )
                self.last_status_code = response.status_code
                self.last_latency_ms = round((perf_counter() - started) * 1000, 1)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderError(f"temporary API-Football response: {response.status_code}")
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get("response"), (list, dict)):
                    raise ProviderError("API-Football response schema is invalid")
                errors = body.get("errors")
                if errors and errors != [] and errors != {}:
                    raise ProviderError(f"API-Football returned provider errors: {errors}")
                remaining = response.headers.get("x-ratelimit-requests-remaining")
                self.rate_limit_remaining = (
                    int(remaining) if remaining and remaining.isdigit() else None
                )
                records = body["response"]
                self.last_payload_hash = payload_hash(records)
                if isinstance(records, list):
                    return [record for record in records if isinstance(record, dict)]
                if isinstance(records, dict):
                    return records
                raise ProviderError("Invalid provider records")
            except (httpx.HTTPError, ProviderError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.4 * (2**attempt))
        raise ProviderError("API-Football request failed after retries") from last_error

    async def get_fixtures(self, date_from: datetime, date_to: datetime) -> list[dict[str, Any]]:
        rows = await self._request(
            "fixtures",
            {
                "from": date_from.date().isoformat(),
                "to": date_to.date().isoformat(),
                "timezone": "UTC",
            },
        )
        return rows if isinstance(rows, list) else []

    async def get_team_stats(
        self, team_external_id: str, competition_external_id: str, season: int
    ) -> dict[str, Any]:
        rows = await self._request(
            "teams/statistics",
            {"team": team_external_id, "league": competition_external_id, "season": str(season)},
        )
        if isinstance(rows, dict):
            return rows
        return rows[0] if rows else {}

    async def get_player_stats(self, player_external_id: str, season: int) -> dict[str, Any]:
        rows = await self._request("players", {"id": player_external_id, "season": str(season)})
        if isinstance(rows, dict):
            return rows
        return rows[0] if rows else {}

    async def get_standings(
        self, competition_external_id: str, season: int
    ) -> list[dict[str, Any]]:
        rows = await self._request(
            "standings", {"league": competition_external_id, "season": str(season)}
        )
        return rows if isinstance(rows, list) else [rows]

    async def get_fixture_statistics(self, event_external_id: str) -> list[dict[str, Any]]:
        rows = await self._request("fixtures/statistics", {"fixture": event_external_id})
        return rows if isinstance(rows, list) else [rows]

    async def get_injuries(self, event_external_id: str) -> list[dict[str, Any]]:
        rows = await self._request("injuries", {"fixture": event_external_id})
        return rows if isinstance(rows, list) else [rows]

    async def get_suspensions(self, event_external_id: str) -> list[dict[str, Any]]:
        rows = await self.get_injuries(event_external_id)
        return [
            row
            for row in rows
            if "suspend" in str(row.get("player", {}).get("reason", "")).lower()
            or "card" in str(row.get("player", {}).get("reason", "")).lower()
        ]

    async def get_lineups(self, event_external_id: str) -> list[dict[str, Any]]:
        rows = await self._request("fixtures/lineups", {"fixture": event_external_id})
        return rows if isinstance(rows, list) else [rows]

    async def get_historical_matches(self, team_external_id: str) -> list[dict[str, Any]]:
        rows = await self._request(
            "fixtures", {"team": team_external_id, "last": "20", "timezone": "UTC"}
        )
        return rows if isinstance(rows, list) else []
