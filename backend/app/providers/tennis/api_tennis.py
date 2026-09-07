import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import TennisProvider
from app.providers.odds.the_odds_api import ProviderError, payload_hash
from app.providers.retry import retry_delay


class ApiTennisProvider(TennisProvider):
    """Current-match adapter for api-tennis.com."""

    def __init__(self, settings: Settings) -> None:
        if not settings.api_tennis_key:
            raise ValueError("API_TENNIS_KEY is not configured")
        self._api_key = settings.api_tennis_key
        self._base_url = settings.api_tennis_base_url
        self._timeout = settings.provider_timeout_seconds
        self.last_latency_ms: float | None = None
        self.last_status_code: int | None = None
        self.last_payload_hash: str | None = None

    async def _request(self, method: str, params: dict[str, str] | None = None) -> Any:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        request_params = {"method": method, "APIkey": self._api_key, **(params or {})}
        last_error: Exception | None = None
        for attempt in range(3):
            started = perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(self._base_url, params=request_params)
                self.last_status_code = response.status_code
                if response.status_code == 429:
                    delay = retry_delay(response.headers.get("Retry-After"), attempt)
                    if delay > 60:
                        raise PermissionError("API Tennis rate limit: defer and resume later")
                    await asyncio.sleep(delay)
                if response.status_code in {401, 403}:
                    raise PermissionError(f"API Tennis access denied: {response.status_code}")
                self.last_latency_ms = round((perf_counter() - started) * 1000, 1)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderError(f"temporary API Tennis response: {response.status_code}")
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or int(body.get("success", 0)) != 1:
                    raise ProviderError("API Tennis returned an unsuccessful response")
                result = body.get("result", [])
                self.last_payload_hash = payload_hash(result)
                return result
            except (httpx.HTTPError, ProviderError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.4 * (2**attempt))
        raise ProviderError("API Tennis request failed after retries") from last_error

    @staticmethod
    def _records(result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [item for item in result.values() if isinstance(item, dict)]
        return []

    async def get_events(self) -> list[dict[str, Any]]:
        return self._records(await self._request("get_events"))

    async def get_matches(self, date_from: datetime, date_to: datetime) -> list[dict[str, Any]]:
        return self._records(
            await self._request(
                "get_fixtures",
                {
                    "date_start": date_from.date().isoformat(),
                    "date_stop": date_to.date().isoformat(),
                    "timezone": "UTC",
                },
            )
        )

    async def get_rankings(self, tour: str) -> list[dict[str, Any]]:
        return self._records(await self._request("get_standings", {"event_type": tour.upper()}))

    async def get_player_history(self, player_external_id: str) -> list[dict[str, Any]]:
        end = datetime.now(UTC)
        start = end - timedelta(days=365)
        return self._records(
            await self._request(
                "get_fixtures",
                {
                    "date_start": start.date().isoformat(),
                    "date_stop": end.date().isoformat(),
                    "player_key": player_external_id,
                    "timezone": "UTC",
                },
            )
        )

    async def get_surface_stats(self, player_external_id: str) -> dict[str, Any]:
        players = await self.get_players(player_external_id)
        return players[0] if players else {}

    async def get_match_stats(self, event_external_id: str) -> dict[str, Any]:
        records = self._records(
            await self._request("get_fixtures", {"match_key": event_external_id})
        )
        return records[0] if records else {}

    async def get_tournament_info(self, tournament_external_id: str) -> dict[str, Any]:
        records = self._records(
            await self._request("get_events", {"event_type_key": tournament_external_id})
        )
        return records[0] if records else {}

    async def get_players(self, player_external_id: str | None = None) -> list[dict[str, Any]]:
        params = {"player_key": player_external_id} if player_external_id else {}
        return self._records(await self._request("get_players", params))

    async def get_h2h(
        self, first_player_external_id: str, second_player_external_id: str
    ) -> list[dict[str, Any]]:
        return self._records(
            await self._request(
                "get_H2H",
                {
                    "first_player_key": first_player_external_id,
                    "second_player_key": second_player_external_id,
                },
            )
        )

    async def get_odds(self, date_from: datetime, date_to: datetime) -> dict[str, Any]:
        result = await self._request(
            "get_odds",
            {
                "date_start": date_from.date().isoformat(),
                "date_stop": date_to.date().isoformat(),
            },
        )
        return result if isinstance(result, dict) else {}
