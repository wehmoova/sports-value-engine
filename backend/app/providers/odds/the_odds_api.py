import asyncio
import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.base import (
    AvailableSport,
    NormalizedEvent,
    NormalizedOdd,
    OddsProvider,
    ProviderBatch,
)

SPORT_PREFIX_MAP = {
    "soccer": "football",
    "tennis_atp": "tennis_atp",
    "tennis_wta": "tennis_wta",
}
MARKET_MAP = {"h2h": "MONEYLINE", "spreads": "HANDICAP", "totals": "TOTALS"}
FOOTBALL_TARGET_TERMS = (
    "bundesliga",
    "premier league",
    " epl",
    "la liga",
    "serie a",
    "ligue 1",
    "champions league",
)


class ProviderError(RuntimeError):
    pass


def payload_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _header_int(response: httpx.Response, name: str) -> int | None:
    raw = response.headers.get(name)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


class TheOddsApiProvider(OddsProvider):
    """Validated, quota-aware adapter for The Odds API v4."""

    def __init__(self, settings: Settings) -> None:
        if not settings.the_odds_api_key:
            raise ValueError("THE_ODDS_API_KEY is not configured")
        self._api_key = settings.the_odds_api_key
        self._base_url = settings.the_odds_api_base_url.rstrip("/")
        self._timeout = settings.provider_timeout_seconds
        self._regions = settings.odds_regions
        self._markets = settings.odds_markets
        self._max_sports = settings.odds_max_sports_per_sync
        self._quota_floor = settings.odds_quota_floor
        self.last_latency_ms: float | None = None
        self.requests_remaining: int | None = None
        self.requests_used: int | None = None
        self.last_request_cost: int | None = None
        self.last_status_code: int | None = None
        self.last_request_at: datetime | None = None

    async def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        request_params = {**params, "apiKey": self._api_key}
        last_error: Exception | None = None
        for attempt in range(3):
            started = perf_counter()
            self.last_request_at = datetime.now(UTC)
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(f"{self._base_url}{path}", params=request_params)
                self.last_latency_ms = round((perf_counter() - started) * 1000, 1)
                self.last_status_code = response.status_code
                self.requests_remaining = _header_int(response, "x-requests-remaining")
                self.requests_used = _header_int(response, "x-requests-used")
                self.last_request_cost = _header_int(response, "x-requests-last")
                if response.status_code == 429 or response.status_code >= 500:
                    raise ProviderError(f"temporary provider response: {response.status_code}")
                response.raise_for_status()
                return response
            except (httpx.HTTPError, ProviderError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.4 * (2**attempt))
        raise ProviderError("The Odds API request failed after retries") from last_error

    @staticmethod
    def _sport(raw_key: str) -> str | None:
        for prefix, internal in SPORT_PREFIX_MAP.items():
            if raw_key.startswith(prefix):
                return internal
        return None

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime:
        if not value:
            raise ValueError("Missing provider timestamp")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def select_target_sports(available: list[AvailableSport]) -> list[AvailableSport]:
        selected: list[AvailableSport] = []
        for sport in available:
            searchable = f" {sport.key.replace('_', ' ')} {sport.title}".lower()
            is_football = sport.group.lower() == "soccer" and any(
                term in searchable for term in FOOTBALL_TARGET_TERMS
            )
            is_tennis = sport.group.lower() == "tennis" and (
                "atp" in searchable or "wta" in searchable
            )
            if sport.active and not sport.has_outrights and (is_football or is_tennis):
                selected.append(sport)
        return sorted(selected, key=lambda item: item.key)

    async def get_available_sports(self) -> list[AvailableSport]:
        response = await self._request("/sports", {"all": "false"})
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("The Odds API sports response is not a list")
        sports: list[AvailableSport] = []
        for item in payload:
            try:
                sports.append(AvailableSport.model_validate(item))
            except ValidationError:
                continue
        return sports

    def _parse(self, payload: list[dict[str, Any]], response: httpx.Response) -> ProviderBatch:
        events: list[NormalizedEvent] = []
        odds: list[NormalizedOdd] = []
        hashes: list[str] = []
        now = datetime.now(UTC)
        for item in payload:
            sport = self._sport(str(item.get("sport_key", "")))
            if sport is None:
                continue
            item_hash = payload_hash(item)
            hashes.append(item_hash)
            try:
                event = NormalizedEvent(
                    external_id=str(item["id"]),
                    sport=sport,
                    competition=str(item.get("sport_title") or item.get("sport_key") or "Unknown"),
                    competition_key=str(item.get("sport_key") or ""),
                    home_name=str(item["home_team"]),
                    away_name=str(item["away_team"]),
                    start_time=self._parse_timestamp(str(item["commence_time"])),
                    source_timestamp=now,
                    source_updated_at=self._parse_timestamp(item.get("last_update"))
                    if item.get("last_update")
                    else None,
                    raw_payload_hash=item_hash,
                )
            except (KeyError, ValidationError, ValueError):
                continue
            events.append(event)
            for bookmaker in item.get("bookmakers", []):
                book_name = str(bookmaker.get("title") or bookmaker.get("key") or "Unknown")
                try:
                    updated_at = self._parse_timestamp(bookmaker.get("last_update"))
                except (ValueError, TypeError):
                    continue
                for market in bookmaker.get("markets", []):
                    market_name = MARKET_MAP.get(
                        str(market.get("key")), str(market.get("key", "UNKNOWN")).upper()
                    )
                    market_time = (
                        self._parse_timestamp(market.get("last_update"))
                        if market.get("last_update")
                        else updated_at
                    )
                    for outcome in market.get("outcomes", []):
                        try:
                            odds.append(
                                NormalizedOdd(
                                    event_external_id=event.external_id,
                                    bookmaker=book_name,
                                    market=market_name,
                                    selection=str(outcome["name"]),
                                    decimal_odds=float(outcome["price"]),
                                    point=float(outcome["point"])
                                    if outcome.get("point") is not None
                                    else None,
                                    timestamp=market_time,
                                    is_live=False,
                                )
                            )
                        except (KeyError, TypeError, ValueError, ValidationError):
                            continue
        return ProviderBatch(
            events=events,
            odds=odds,
            requests_remaining=_header_int(response, "x-requests-remaining"),
            requests_used=_header_int(response, "x-requests-used"),
            last_request_cost=_header_int(response, "x-requests-last"),
            payload_hashes=hashes,
        )

    async def get_target_odds(self) -> ProviderBatch:
        available = await self.get_available_sports()
        targets = self.select_target_sports(available)[: self._max_sports]
        combined = ProviderBatch(events=[], odds=[])
        for target in targets:
            if self.requests_remaining is not None and self.requests_remaining <= self._quota_floor:
                break
            batch = await self.get_odds(target.key)
            combined.events.extend(batch.events)
            combined.odds.extend(batch.odds)
            combined.payload_hashes.extend(batch.payload_hashes)
            combined.requested_sport_keys.append(target.key)
            combined.requests_remaining = batch.requests_remaining
            combined.requests_used = batch.requests_used
            combined.last_request_cost = batch.last_request_cost
        return combined

    async def get_events(self, sport_keys: list[str] | None = None) -> list[NormalizedEvent]:
        keys = sport_keys
        if keys is None:
            keys = [
                sport.key for sport in self.select_target_sports(await self.get_available_sports())
            ]
        events: list[NormalizedEvent] = []
        for key in keys[: self._max_sports]:
            events.extend((await self.get_odds(key)).events)
        return events

    async def get_odds(self, sport_key: str = "upcoming") -> ProviderBatch:
        response = await self._request(
            f"/sports/{sport_key}/odds",
            {
                "regions": self._regions,
                "markets": self._markets,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise ProviderError("The Odds API odds response is not a list")
        batch = self._parse(payload, response)
        batch.requested_sport_keys = [sport_key]
        return batch

    async def get_event_odds(self, sport_key: str, event_id: str) -> ProviderBatch:
        response = await self._request(
            f"/sports/{sport_key}/events/{event_id}/odds",
            {"regions": self._regions, "markets": self._markets, "oddsFormat": "decimal"},
        )
        payload = response.json()
        return self._parse([payload] if isinstance(payload, dict) else payload, response)

    async def get_historical_odds(
        self, sport_key: str, event_id: str, snapshot_at: datetime
    ) -> ProviderBatch:
        response = await self._request(
            f"/historical/sports/{sport_key}/events/{event_id}/odds",
            {
                "regions": self._regions,
                "markets": self._markets,
                "oddsFormat": "decimal",
                "date": snapshot_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            },
        )
        body = response.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        return self._parse([data] if isinstance(data, dict) else data, response)

    async def get_markets(self) -> list[str]:
        return [MARKET_MAP.get(key, key.upper()) for key in self._markets.split(",")]
