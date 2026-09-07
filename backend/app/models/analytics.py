from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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


class ModelPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_predictions"
    __table_args__ = (Index("ix_predictions_event_market", "event_id", "market"),)

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    market: Mapped[str] = mapped_column(String(80))
    selection: Mapped[str] = mapped_column(String(180))
    market_point: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(100))
    model_probability: Mapped[float] = mapped_column(Float)
    probability_low: Mapped[float | None] = mapped_column(Float)
    probability_high: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(80))
    feature_version: Mapped[str] = mapped_column(String(80))
    training_period: Mapped[str | None] = mapped_column(String(120))
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    data_snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    components: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    explanation_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_factors: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_demo: Mapped[bool] = mapped_column(default=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="REAL", index=True)
    calibration_method: Mapped[str | None] = mapped_column(String(40))
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_status_created", "status", "created_at"),)

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_predictions.id", ondelete="SET NULL")
    )
    market: Mapped[str] = mapped_column(String(80))
    selection: Mapped[str] = mapped_column(String(180))
    market_point: Mapped[float | None] = mapped_column(Float)
    bookmaker: Mapped[str | None] = mapped_column(String(120))
    best_odds: Mapped[float] = mapped_column(Float)
    average_odds: Mapped[float] = mapped_column(Float)
    median_odds: Mapped[float] = mapped_column(Float)
    opening_odds: Mapped[float | None] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)
    market_probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[int] = mapped_column(Integer)
    data_quality_score: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), index=True)
    reason_code: Mapped[str] = mapped_column(String(80))
    desired_entry_odds: Mapped[float | None] = mapped_column(Float)
    odds_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(default=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="REAL", index=True)
    prediction_odds: Mapped[float | None] = mapped_column(Float)
    best_odds_at_prediction: Mapped[float | None] = mapped_column(Float)
    consensus_odds_at_prediction: Mapped[float | None] = mapped_column(Float)
    closing_best_odds: Mapped[float | None] = mapped_column(Float)
    closing_consensus_odds: Mapped[float | None] = mapped_column(Float)
    data_quality_components: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    eligibility_checks: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), index=True)


class CombinationRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "combination_recommendations"

    category: Mapped[str] = mapped_column(String(40), index=True)
    leg_ids: Mapped[list[str]] = mapped_column(JSON)
    combined_odds: Mapped[float] = mapped_column(Float)
    combined_probability: Mapped[float] = mapped_column(Float)
    combined_ev: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[int] = mapped_column(Integer)
    correlation_warning: Mapped[str | None] = mapped_column(String(300))
    independence_assumed: Mapped[bool] = mapped_column(default=True)
    is_demo: Mapped[bool] = mapped_column(default=False)


class BetResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bet_results"
    __table_args__ = (UniqueConstraint("recommendation_id", name="settled_recommendation"),)

    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    result: Mapped[str] = mapped_column(String(20), index=True)
    odds_at_prediction: Mapped[float] = mapped_column(Float)
    closing_odds: Mapped[float | None] = mapped_column(Float)
    stake: Mapped[float] = mapped_column(Float)
    profit_loss: Mapped[float] = mapped_column(Float)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BankrollHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "bankroll_history"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    bankroll: Mapped[float] = mapped_column(Float)
    change: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(120))
    bet_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("bet_results.id", ondelete="SET NULL")
    )


class ModelPerformance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_performance"

    model_version: Mapped[str] = mapped_column(String(80), index=True)
    segment: Mapped[str] = mapped_column(String(120), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bets: Mapped[int] = mapped_column(Integer, default=0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    yield_pct: Mapped[float] = mapped_column(Float, default=0.0)
    clv: Mapped[float | None] = mapped_column(Float)
    brier_score: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(default=True)


class AnalysisRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    trigger: Mapped[str] = mapped_column(String(30), default="MANUAL")
    job_type: Mapped[str] = mapped_column(String(40), default="daily_analysis")
    deployment_version: Mapped[str] = mapped_column(String(120), default="development")
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    events_processed: Mapped[int] = mapped_column(Integer, default=0)
    predictions_created: Mapped[int] = mapped_column(Integer, default=0)
    value_picks_created: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(80), default="mvp-ensemble-v1")
    log_summary: Mapped[str | None] = mapped_column(Text)


class AnalysisRunStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_run_steps"
    __table_args__ = (UniqueConstraint("analysis_run_id", "step_name", name="run_step"),)

    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class ModelRegistry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_name", "model_version", "sport", "market", name="registered_model"),
    )

    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(80))
    sport: Mapped[str] = mapped_column(String(40), index=True)
    market: Mapped[str] = mapped_column(String(80), index=True)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    features_version: Mapped[str] = mapped_column(String(80))
    calibration_method: Mapped[str | None] = mapped_column(String(40))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="EXPERIMENTAL", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
