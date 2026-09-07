import json

import pytest

from app.core.config import settings
from app.scripts.verify_providers import verify


async def test_smoke_missing_credentials_has_no_fabricated_proof(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("the_odds_api_key", "sportmonks_api_token", "api_football_key", "api_tennis_key"):
        monkeypatch.setattr(settings, name, None)
    assert await verify() == 1
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(records) == 3
    assert all(row["status"] == "NOT_CONFIGURED" for row in records)
    assert all("event_proof" not in row and "http_status" not in row for row in records)
