"""Real network smoke test, independent of the database. Never prints raw errors/URLs."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.providers.football import ApiFootballProvider, SportmonksFootballProvider
from app.providers.odds import TheOddsApiProvider
from app.providers.tennis import ApiTennisProvider
from app.scripts.sportmonks_smoke import verify_sportmonks
from app.services.football_sync import normalize_football_fixture
from app.services.tennis_sync import normalize_tennis_fixture


async def verify() -> int:
    # HTTP client INFO logs can contain query-string credentials.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    specifications = [
        ("THE ODDS API", bool(settings.the_odds_api_key), TheOddsApiProvider),
        (
            settings.football_provider.upper(),
            settings.football_provider_configured,
            SportmonksFootballProvider
            if settings.football_provider == "sportmonks"
            else ApiFootballProvider,
        ),
        ("API TENNIS", settings.tennis_provider_configured, ApiTennisProvider),
    ]
    complete = True
    for name, configured, factory in specifications:
        if factory is SportmonksFootballProvider:
            sportmonks_result = await verify_sportmonks(settings)
            complete = complete and sportmonks_result["status"] == "VERIFIED"
            print(json.dumps(sportmonks_result, ensure_ascii=True))
            continue
        result: dict[str, Any] = {"provider": name, "configured": configured}
        if not configured:
            result["status"] = "NOT_CONFIGURED"
            complete = False
        else:
            provider = factory(settings)
            try:
                now = datetime.now(UTC)
                events = []
                if isinstance(provider, TheOddsApiProvider):
                    batch = await provider.get_target_odds()
                    events = batch.events
                    result["records_received"] = len(events)
                else:
                    raw = (
                        await provider.get_matches(now, now + timedelta(days=1))
                        if isinstance(provider, ApiTennisProvider)
                        else await provider.get_fixtures(now, now + timedelta(days=1))
                    )
                    result["records_received"] = len(raw)
                    for item in raw:
                        try:
                            events.append(
                                normalize_tennis_fixture(item)
                                if isinstance(provider, ApiTennisProvider)
                                else normalize_football_fixture(item, settings.football_provider)
                            )
                        except (ValueError, TypeError, KeyError):
                            continue
                result["http_status"] = provider.last_status_code
                result["events_validated"] = len(events)
                result["status"] = "VERIFIED" if events else "REQUEST_SUCCEEDED_NO_EVENT_PROOF"
                if not events:
                    complete = False
                else:
                    event = events[0]
                    result["event_proof"] = {
                        "provider": name,
                        "external_event_id": event.external_id,
                        "competition": event.competition,
                        "participants": [event.home_name, event.away_name],
                        "commence_time": event.start_time.isoformat(),
                        "fetched_at": datetime.now(UTC).isoformat(),
                        "data_origin": "real",
                    }
            except Exception as exc:
                complete = False
                result.update(
                    status="FAILED",
                    http_status=provider.last_status_code,
                    error_type=type(exc).__name__,
                )
        print(json.dumps(result, ensure_ascii=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
