"""Plan-independent Sportmonks authentication smoke test."""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings


def redact(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if re.search(r"token|secret|password|authorization|api.?key", str(key), re.I)
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]").replace(
                    quote(secret, safe=""), "[REDACTED]"
                )
        value = re.sub(r"(?i)(Bearer\s+)[^\s\"<>]+", r"\1[REDACTED]", value)
        return re.sub(
            r"(?i)((?:api_token|api_key|apikey|token)=)[^&\s\"<>]+", r"\1[REDACTED]", value
        )
    return value


async def verify_sportmonks(config: Settings) -> dict[str, Any]:
    token = config.sportmonks_api_token
    result: dict[str, Any] = {"provider": "SPORTMONKS", "configured": bool(token)}
    if not token:
        return {**result, "status": "NOT_CONFIGURED"}
    secrets = [
        value
        for name, value in config.model_dump().items()
        if isinstance(value, str) and re.search(r"key|token|secret|password", name)
    ]
    try:
        async with httpx.AsyncClient(timeout=config.provider_timeout_seconds) as client:
            response = await client.get(
                "https://api.sportmonks.com/v3/football/leagues",
                headers={"Authorization": f"Bearer {token}"},
            )
            result["auth_method"] = "bearer"
            if response.status_code == 401:
                result["bearer_http_status"] = 401
                response = await client.get(
                    "https://api.sportmonks.com/v3/football/leagues",
                    params={"api_token": token},
                )
                result["auth_method"] = "query"
        result.update(http_status=response.status_code, fetched_at=datetime.now(UTC).isoformat())
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.status_code == 403:
            result["response_body"] = redact(body, secrets)
        if response.status_code != 200:
            return {
                **result,
                "status": "FAILED",
                "base_api": "FAILED",
                "leagues": "FORBIDDEN" if response.status_code == 403 else "UNAVAILABLE",
            }
        rows = body.get("data") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            return {
                **result,
                "status": "FAILED",
                "base_api": "VERIFIED",
                "error_type": "InvalidLeagueResponse",
            }
        leagues = [row for row in rows if isinstance(row, dict)]
        result.update(
            status="VERIFIED",
            base_api="VERIFIED",
            leagues="AVAILABLE",
            records_received=len(rows),
            access_proof=redact(
                {"league_id": leagues[0].get("id"), "name": leagues[0].get("name")}
                if leagues
                else None,
                secrets,
            ),
        )
        return result
    except httpx.HTTPError as exc:
        return {
            **result,
            "status": "FAILED",
            "base_api": "FAILED",
            "error_type": type(exc).__name__,
        }
