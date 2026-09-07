from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="provider_external_event"),
        UniqueConstraint("canonical_key", name="canonical_event"),
        Index("ix_events_sport_start", "sport_id", "start_time"),
    )

    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id", ondelete="CASCADE"))
    competition_id: Mapped[str | None] = mapped_column(
        ForeignKey("competitions.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str] = mapped_column(String(180))
    canonical_key: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(360))
    home_name: Mapped[str] = mapped_column(String(180))
    away_name: Mapped[str] = mapped_column(String(180))
    home_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    away_entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED", index=True)
    home_score: Mapped[float | None] = mapped_column(Float)
    away_score: Mapped[float | None] = mapped_column(Float)
    winner_name: Mapped[str | None] = mapped_column(String(180))
    venue: Mapped[str | None] = mapped_column(String(180))
    surface: Mapped[str | None] = mapped_column(String(30))
    round: Mapped[str | None] = mapped_column(String(60))
    best_of: Mapped[int | None] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(default=False, index=True)
    data_origin: Mapped[str] = mapped_column(String(20), default="REAL", index=True)
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_provider: Mapped[str] = mapped_column(String(80), default="unknown")
    provider_entity_id: Mapped[str | None] = mapped_column(String(180), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class FootballStatistic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "football_statistics"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "team_id", "side", "observed_at", name="football_stat_snapshot"
        ),
    )

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str | None] = mapped_column(String(36), index=True)
    side: Mapped[str] = mapped_column(String(10))
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    goals_per_match: Mapped[float | None] = mapped_column(Float)
    goals_against_per_match: Mapped[float | None] = mapped_column(Float)
    xg_per_match: Mapped[float | None] = mapped_column(Float)
    xga_per_match: Mapped[float | None] = mapped_column(Float)
    shots_per_match: Mapped[float | None] = mapped_column(Float)
    shots_on_target_per_match: Mapped[float | None] = mapped_column(Float)
    form_points: Mapped[float | None] = mapped_column(Float)
    rest_days: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_provider: Mapped[str] = mapped_column(String(80), default="unknown")
    provider_entity_id: Mapped[str | None] = mapped_column(String(180))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class TennisStatistic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tennis_statistics"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "player_id", "side", "observed_at", name="tennis_stat_snapshot"
        ),
    )

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str | None] = mapped_column(String(36), index=True)
    side: Mapped[str] = mapped_column(String(10))
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    ranking: Mapped[int | None] = mapped_column(Integer)
    ranking_points: Mapped[int | None] = mapped_column(Integer)
    overall_elo: Mapped[float | None] = mapped_column(Float)
    surface_elo: Mapped[float | None] = mapped_column(Float)
    hold_pct: Mapped[float | None] = mapped_column(Float)
    break_pct: Mapped[float | None] = mapped_column(Float)
    first_serve_pct: Mapped[float | None] = mapped_column(Float)
    first_serve_won_pct: Mapped[float | None] = mapped_column(Float)
    second_serve_won_pct: Mapped[float | None] = mapped_column(Float)
    return_points_won_pct: Mapped[float | None] = mapped_column(Float)
    matches_last_7_days: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_provider: Mapped[str] = mapped_column(String(80), default="unknown")
    provider_entity_id: Mapped[str | None] = mapped_column(String(180))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class PlayerStatistic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "player_statistics"

    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Injury(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "injuries"

    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    player_id: Mapped[str | None] = mapped_column(String(36), index=True)
    team_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(String(300))
    impact_score: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Suspension(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suspensions"

    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    player_id: Mapped[str | None] = mapped_column(String(36), index=True)
    team_id: Mapped[str | None] = mapped_column(String(36), index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Lineup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lineups"

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str | None] = mapped_column(String(36), index=True)
    player_id: Mapped[str | None] = mapped_column(String(36), index=True)
    player_name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30))
    position: Mapped[str | None] = mapped_column(String(30))
    confirmed: Mapped[bool] = mapped_column(default=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OddsSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        Index("ix_odds_event_market_observed", "event_id", "market", "observed_at"),
        UniqueConstraint("snapshot_key", name="odds_snapshot_key"),
    )

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(80), default="the_odds_api")
    bookmaker: Mapped[str] = mapped_column(String(120), index=True)
    market: Mapped[str] = mapped_column(String(80), index=True)
    selection: Mapped[str] = mapped_column(String(180), index=True)
    snapshot_key: Mapped[str] = mapped_column(String(64), index=True)
    decimal_odds: Mapped[float] = mapped_column(Float)
    point: Mapped[float | None] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_live: Mapped[bool] = mapped_column(default=False)
    is_outlier: Mapped[bool] = mapped_column(default=False)
    validation_status: Mapped[str] = mapped_column(String(20), default="VALID", index=True)
    validation_reason: Mapped[str | None] = mapped_column(Text)
    freshness_status: Mapped[str] = mapped_column(String(20), default="FRESH", index=True)
    odds_age_seconds: Mapped[int] = mapped_column(Integer, default=0)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
