from datetime import UTC, datetime

import httpx

from app.core.config import Settings
from app.providers.odds import TheOddsApiProvider


def test_odds_provider_normalizes_and_rejects_impossible_price() -> None:
    provider = TheOddsApiProvider(Settings(the_odds_api_key="test-key"))
    payload = [
        {
            "id": "event-1",
            "sport_key": "soccer_epl",
            "sport_title": "Premier League",
            "commence_time": "2026-09-03T18:00:00Z",
            "home_team": "Home FC",
            "away_team": "Away FC",
            "bookmakers": [
                {
                    "title": "Example Book",
                    "last_update": "2026-09-02T18:00:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Home FC", "price": 1.9},
                                {"name": "Draw", "price": 3.5},
                                {"name": "Away FC", "price": 0.8},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    request = httpx.Request("GET", "https://example.invalid")
    response = httpx.Response(
        200,
        request=request,
        headers={"x-requests-remaining": "42", "x-requests-used": "8"},
    )
    batch = provider._parse(payload, response)
    assert len(batch.events) == 1
    assert batch.events[0].sport == "football"
    assert len(batch.odds) == 2
    assert batch.requests_remaining == 42
    assert batch.events[0].start_time == datetime(2026, 9, 3, 18, tzinfo=UTC)
