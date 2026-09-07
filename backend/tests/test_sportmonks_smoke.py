import json

import httpx
import pytest

from app.core.config import Settings
from app.scripts.sportmonks_smoke import verify_sportmonks


@pytest.mark.parametrize("status_code", [200, 403])
async def test_leagues_only_and_secret_redaction(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    token = "synthetic-test-secret"
    config = Settings(_env_file=None, sportmonks_api_token=token)
    original_client = httpx.AsyncClient
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/v3/football/leagues"
        assert "include" not in request.url.params
        if request.headers.get("Authorization"):
            return httpx.Response(401)
        assert request.url.params["api_token"] == token
        payload = (
            {"data": [{"id": 123, "name": "Test league"}]}
            if status_code == 200
            else {"api_token": token, "message": f"Forbidden for {token}"}
        )
        return httpx.Response(status_code, json=payload)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await verify_sportmonks(config)
    assert len(requests) == 2
    assert token not in json.dumps(result)
    assert result["http_status"] == status_code
    if status_code == 200:
        assert result["base_api"] == "VERIFIED"
        assert result["records_received"] == 1
        assert result["access_proof"]["league_id"] == 123
    else:
        assert result["leagues"] == "FORBIDDEN"
        assert result["response_body"]["api_token"] == "[REDACTED]"
