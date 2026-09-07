from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.providers.football.sportmonks import SportmonksFootballProvider


async def test_fixture_query_uses_discovered_league_and_no_premium_include() -> None:
    provider = SportmonksFootballProvider(
        Settings(_env_file=None, sportmonks_api_token="test-only")
    )
    provider._request = AsyncMock(side_effect=[[{"id": 123}], [{"id": 5, "league_id": 123}]])
    rows = await provider.get_fixtures(datetime.now(UTC), datetime.now(UTC))
    assert rows[0]["id"] == 5
    calls = provider._request.call_args_list
    assert calls[0].args[0] == "leagues"
    assert calls[1].args[1]["filters"] == "fixtureLeagues:123"
    assert calls[1].args[1]["include"] == "participants;league;state;scores"


async def test_optional_forbidden_does_not_fail_fixture_capability() -> None:
    provider = SportmonksFootballProvider(
        Settings(_env_file=None, sportmonks_api_token="test-only")
    )
    provider.capabilities["fixtures"] = "AVAILABLE"
    provider.last_status_code = 403
    provider._fixture = AsyncMock(side_effect=PermissionError("Forbidden"))
    assert await provider.optional_fixture("5", "xg", "xGFixture") == {}
    assert provider.capabilities == {"fixtures": "AVAILABLE", "xg": "FORBIDDEN"}
