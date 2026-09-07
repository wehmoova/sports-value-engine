from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProviderStatus(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_status"

    provider_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    configured: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(30), default="NOT_CONFIGURED")
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer)
    rate_limit_used: Mapped[int | None] = mapped_column(Integer)
    last_request_cost: Mapped[int | None] = mapped_column(Integer)
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    data_freshness_seconds: Mapped[int | None] = mapped_column(Integer)
    sports_supplied: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_logs"

    provider_name: Mapped[str] = mapped_column(String(100), index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    error_type: Mapped[str | None] = mapped_column(String(100))
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ProviderPayloadAudit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "provider_payload_audits"

    provider_name: Mapped[str] = mapped_column(String(100), index=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_code: Mapped[int | None] = mapped_column(Integer)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    external_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
