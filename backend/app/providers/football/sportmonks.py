import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import FootballProvider
from app.providers.odds.the_odds_api import ProviderError, payload_hash
from app.providers.retry import retry_delay
from app.scripts.sportmonks_smoke import redact


class SportmonksFootballProvider(FootballProvider):
    """Sportmonks Football API v3 adapter using documented fixture includes."""

    def __init__(self, settings: Settings) -> None:
        if not settings.sportmonks_api_token:
            raise ValueError("SPORTMONKS_API_TOKEN is not configured")
        self._token = settings.sportmonks_api_token
        self._base_url = "https://api.sportmonks.com/v3/football"
        self._timeout = settings.provider_timeout_seconds
        self.last_latency_ms: float | None = None
        self.last_status_code: int | None = None
        self.last_payload_hash: str | None = None
        self.last_pagination: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self.accessible_league_ids: list[int] = []

    async def _request(self, path: str, params: dict[str, str] | None = None) -> Any:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        request_params = {"api_token": self._token, **(params or {})}
        last_error: Exception | None = None
        for attempt in range(3):
            started = perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        f"{self._base_url}/{path.lstrip('/')}", params=request_params
                    )
                self.last_status_code = response.status_code
                if response.status_code == 429:
                    delay = retry_delay(response.headers.get("Retry-After"), attempt)
                    if delay > 60:
                        raise PermissionError("Sportmonks rate limit: defer and resume later")
                    await asyncio.sleep(delay)
                self.last_latency_ms = round((perf_counter() - started) * 1000, 1)
                try:
                    diagnostic_body = response.json()
                except ValueError:
                    diagnostic_body = response.text
                self.last_pagination = (
                    diagnostic_body.get("pagination", {})
                    if isinstance(diagnostic_body, dict)
                    else {}
                )
                data_rows = (
                    diagnostic_body.get("data", []) if isinstance(diagnostic_body, dict) else []
                )
                diagnostic = {
                    "provider": "sportmonks",
                    "endpoint": path,
                    "http_status": response.status_code,
                    "records_returned": len(data_rows) if isinstance(data_rows, list) else 1,
                    "pagination": {
                        k: v
                        for k, v in self.last_pagination.items()
                        if k in {"count", "per_page", "has_more", "current_page"}
                    },
                    "requested_league": (params or {}).get("filters"),
                    "requested_date_range": path.split("between/")[-1]
                    if "between/" in path
                    else None,
                }
                if response.status_code >= 400:
                    diagnostic["response_body"] = redact(diagnostic_body, [self._token])
                print(json.dumps(diagnostic, default=str))
                if response.status_code in {400, 401, 403, 404, 422}:
                    raise PermissionError(json.dumps(diagnostic, default=str))
                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderError(f"temporary Sportmonks response: {response.status_code}")
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or "data" not in body:
                    raise ProviderError("Sportmonks response schema is invalid")
                data = body["data"]
                self.last_payload_hash = payload_hash(data)
                return data
            except (httpx.HTTPError, ProviderError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.4 * (2**attempt))
        raise ProviderError("Sportmonks request failed after retries") from last_error

    @staticmethod
    def _records(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return [data] if isinstance(data, dict) else []

    async def _paged(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, 101):
            rows.extend(
                self._records(await self._request(path, {**(params or {}), "page": str(page)}))
            )
            if not self.last_pagination.get("has_more"):
                return rows
        raise ProviderError("Sportmonks pagination exceeded safety limit")

    async def discover_leagues(self) -> list[dict[str, Any]]:
        leagues = await self._paged("leagues")
        self.accessible_league_ids = [int(row["id"]) for row in leagues if row.get("id")]
        self.capabilities.update(
            authentication="VERIFIED",
            leagues="AVAILABLE",
            accessible_league_ids=self.accessible_league_ids,
        )
        return leagues

    async def get_fixtures(self, date_from: datetime, date_to: datetime) -> list[dict[str, Any]]:
        if not self.accessible_league_ids:
            await self.discover_leagues()
        rows = []
        for league_id in self.accessible_league_ids:
            rows.extend(
                await self._paged(
                    f"fixtures/between/{date_from.date().isoformat()}/{date_to.date().isoformat()}",
                    {
                        "filters": f"fixtureLeagues:{league_id}",
                        "include": "participants;league;state;scores",
                    },
                )
            )
        self.capabilities["fixtures"] = "AVAILABLE" if rows else "EMPTY"
        return rows

    async def optional_fixture(
        self, fixture_id: str, capability: str, include: str
    ) -> dict[str, Any]:
        try:
            data = await self._fixture(fixture_id, include)
            self.capabilities[capability] = "AVAILABLE"
            return data
        except (PermissionError, ProviderError):
            self.capabilities[capability] = (
                "FORBIDDEN" if self.last_status_code == 403 else "FAILED"
            )
            return {}

    async def get_team_stats(
        self, team_external_id: str, competition_external_id: str, season: int
    ) -> dict[str, Any]:
        del competition_external_id, season
        records = self._records(
            await self._request(f"teams/{team_external_id}", {"include": "statistics"})
        )
        return records[0] if records else {}

    async def get_player_stats(self, player_external_id: str, season: int) -> dict[str, Any]:
        del season
        records = self._records(
            await self._request(f"players/{player_external_id}", {"include": "statistics"})
        )
        return records[0] if records else {}

    async def get_standings(
        self, competition_external_id: str, season: int
    ) -> list[dict[str, Any]]:
        del competition_external_id
        return self._records(await self._request(f"standings/seasons/{season}"))

    async def _fixture(self, event_external_id: str, include: str) -> dict[str, Any]:
        records = self._records(
            await self._request(f"fixtures/{event_external_id}", {"include": include})
        )
        return records[0] if records else {}

    async def get_fixture_statistics(self, event_external_id: str) -> list[dict[str, Any]]:
        fixture = await self._fixture(event_external_id, "statistics.type")
        statistics = fixture.get("statistics", [])
        return [item for item in statistics if isinstance(item, dict)]

    async def get_injuries(self, event_external_id: str) -> list[dict[str, Any]]:
        fixture = await self._fixture(event_external_id, "sidelined.sideline;sidelined.player")
        return [item for item in fixture.get("sidelined", []) if isinstance(item, dict)]

    async def get_suspensions(self, event_external_id: str) -> list[dict[str, Any]]:
        rows = await self.get_injuries(event_external_id)
        return [
            row
            for row in rows
            if "suspend" in str(row.get("sideline", {}).get("name", "")).lower()
            or "card" in str(row.get("sideline", {}).get("name", "")).lower()
        ]

    async def get_lineups(self, event_external_id: str) -> list[dict[str, Any]]:
        fixture = await self._fixture(event_external_id, "lineups.player;expectedLineups.player")
        rows = fixture.get("lineups", []) or fixture.get("expected_lineups", [])
        return [item for item in rows if isinstance(item, dict)]

    async def get_historical_matches(self, team_external_id: str) -> list[dict[str, Any]]:
        end = datetime.now(UTC)
        start = end - timedelta(days=365)
        data = await self._request(
            f"fixtures/between/{start.date().isoformat()}/{end.date().isoformat()}/{team_external_id}",
            {"include": "participants;scores;league;state"},
        )
        return self._records(data)
