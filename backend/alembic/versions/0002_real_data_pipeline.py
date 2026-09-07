"""Real-data provenance, provider diagnostics and idempotency fields.

Revision ID: 0002_real_data_pipeline
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app import models  # noqa: F401
from app.database.base import Base

revision: str = "0002_real_data_pipeline"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_missing_columns(table_name: str, columns: list[sa.Column[object]]) -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    _add_missing_columns(
        "events",
        [
            sa.Column("canonical_key", sa.String(64), nullable=True),
            sa.Column("data_origin", sa.String(20), nullable=False, server_default="REAL"),
            sa.Column("source_provider", sa.String(80), nullable=False, server_default="unknown"),
            sa.Column("home_score", sa.Float(), nullable=True),
            sa.Column("away_score", sa.Float(), nullable=True),
            sa.Column("winner_name", sa.String(180), nullable=True),
            sa.Column("provider_entity_id", sa.String(180), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_payload_hash", sa.String(64), nullable=True),
            sa.Column("ingestion_run_id", sa.String(36), nullable=True),
        ],
    )
    provenance_columns = [
        sa.Column("source_provider", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("provider_entity_id", sa.String(180), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_hash", sa.String(64), nullable=True),
        sa.Column("ingestion_run_id", sa.String(36), nullable=True),
    ]
    _add_missing_columns("football_statistics", provenance_columns)
    _add_missing_columns(
        "tennis_statistics",
        [
            sa.Column("source_provider", sa.String(80), nullable=False, server_default="unknown"),
            sa.Column("provider_entity_id", sa.String(180), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_payload_hash", sa.String(64), nullable=True),
            sa.Column("ingestion_run_id", sa.String(36), nullable=True),
        ],
    )
    _add_missing_columns(
        "odds_snapshots",
        [
            sa.Column("snapshot_key", sa.String(64), nullable=True),
            sa.Column("validation_status", sa.String(20), nullable=False, server_default="VALID"),
            sa.Column("validation_reason", sa.Text(), nullable=True),
            sa.Column("freshness_status", sa.String(20), nullable=False, server_default="FRESH"),
            sa.Column("odds_age_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_payload_hash", sa.String(64), nullable=True),
            sa.Column("ingestion_run_id", sa.String(36), nullable=True),
        ],
    )
    _add_missing_columns(
        "model_predictions",
        [
            sa.Column("data_origin", sa.String(20), nullable=False, server_default="REAL"),
            sa.Column("calibration_method", sa.String(40), nullable=True),
            sa.Column("market_point", sa.Float(), nullable=True),
            sa.Column("is_calibrated", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("ingestion_run_id", sa.String(36), nullable=True),
        ],
    )
    _add_missing_columns(
        "recommendations",
        [
            sa.Column("data_origin", sa.String(20), nullable=False, server_default="REAL"),
            sa.Column("market_point", sa.Float(), nullable=True),
            sa.Column("prediction_odds", sa.Float(), nullable=True),
            sa.Column("best_odds_at_prediction", sa.Float(), nullable=True),
            sa.Column("consensus_odds_at_prediction", sa.Float(), nullable=True),
            sa.Column("closing_best_odds", sa.Float(), nullable=True),
            sa.Column("closing_consensus_odds", sa.Float(), nullable=True),
            sa.Column("data_quality_components", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("eligibility_checks", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("ingestion_run_id", sa.String(36), nullable=True),
        ],
    )
    _add_missing_columns(
        "provider_status",
        [
            sa.Column("configured", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rate_limit_used", sa.Integer(), nullable=True),
            sa.Column("last_request_cost", sa.Integer(), nullable=True),
            sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("data_freshness_seconds", sa.Integer(), nullable=True),
            sa.Column("sports_supplied", sa.JSON(), nullable=False, server_default="[]"),
        ],
    )


def downgrade() -> None:
    # This migration intentionally keeps provenance/audit data on downgrade.
    pass
