from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import ResearchArtifact
from app.providers.odds.the_odds_api import payload_hash


async def artifact(
    session: AsyncSession,
    kind: str,
    sport: str,
    payload: dict[str, Any],
    *,
    status: str = "COMPLETED",
    key: str | None = None,
) -> ResearchArtifact:
    identity = key or payload_hash({"sport": sport, "payload": payload})
    existing = await session.scalar(
        select(ResearchArtifact).where(
            ResearchArtifact.kind == kind,
            ResearchArtifact.artifact_key == identity,
        )
    )
    if existing is not None:
        return existing
    row = ResearchArtifact(
        kind=kind, artifact_key=identity, sport=sport, status=status, payload=payload
    )
    session.add(row)
    await session.flush()
    return row
