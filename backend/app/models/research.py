"""Versioned research evidence, separate from production predictions and picks."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now


class ResearchArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "research_artifacts"
    __table_args__ = (UniqueConstraint("kind", "artifact_key", name="research_artifact_key"),)

    kind: Mapped[str] = mapped_column(String(40), index=True)
    artifact_key: Mapped[str] = mapped_column(String(180))
    sport: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
