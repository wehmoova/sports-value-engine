"""Real, opt-in network requests; missing credentials skip rather than simulate."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.providers.football import ApiFootballProvider, SportmonksFootballProvider
from app.providers.odds import TheOddsApiProvider
from app.providers.tennis import ApiTennisProvider

pytestmark = pytest.mark.integration


async def test_live_odds_metadata() -> None:
    if not settings.the_odds_api_key:
        pytest.skip("NOT VERIFIED — KEY MISSING")
    assert isinstance(await TheOddsApiProvider(settings).get_available_sports(), list)


async def test_live_football() -> None:
    if not settings.football_provider_configured:
        pytest.skip("NOT VERIFIED — KEY MISSING")
    provider = (
        ApiFootballProvider(settings)
        if settings.football_provider == "api_football"
        else SportmonksFootballProvider(settings)
    )
    now = datetime.now(UTC)
    assert isinstance(await provider.get_fixtures(now, now + timedelta(days=1)), list)


async def test_live_tennis() -> None:
    if not settings.tennis_provider_configured:
        pytest.skip("NOT VERIFIED — KEY MISSING")
    assert isinstance(await ApiTennisProvider(settings).get_rankings("ATP"), list)
