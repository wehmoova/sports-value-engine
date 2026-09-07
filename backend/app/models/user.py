from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Analyst")
    is_active: Mapped[bool] = mapped_column(default=True)


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    min_odds: Mapped[float] = mapped_column(Float, default=1.45)
    min_edge: Mapped[float] = mapped_column(Float, default=0.03)
    min_ev: Mapped[float] = mapped_column(Float, default=0.03)
    min_confidence: Mapped[int] = mapped_column(Integer, default=70)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Berlin")
    odds_format: Mapped[str] = mapped_column(String(20), default="DECIMAL")
    sports_enabled: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["football", "tennis"])
    notifications_enabled: Mapped[bool] = mapped_column(default=False)
    auto_refresh_minutes: Mapped[int] = mapped_column(Integer, default=15)


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "event_id", "market", "selection"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    market: Mapped[str] = mapped_column(String(80))
    selection: Mapped[str] = mapped_column(String(180))
    desired_entry_odds: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
