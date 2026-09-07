"""Persist cloud job metadata and upgrade idempotency indexes."""

import sqlalchemy as sa

from alembic import op

revision = "0003_cloud_jobs"
down_revision = "0002_real_data_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.models.system import WorkerHeartbeat

    WorkerHeartbeat.__table__.create(bind, checkfirst=True)
    existing = {c["name"] for c in sa.inspect(bind).get_columns("analysis_runs")}
    for column in [
        sa.Column("job_type", sa.String(40), nullable=False, server_default="daily_analysis"),
        sa.Column(
            "deployment_version", sa.String(120), nullable=False, server_default="development"
        ),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
    ]:
        if column.name not in existing:
            op.add_column("analysis_runs", column)
    for table, column, name in [
        ("odds_snapshots", "snapshot_key", "uq_odds_snapshot_key_upgrade"),
        ("events", "canonical_key", "uq_event_canonical_key_upgrade"),
        ("bet_results", "recommendation_id", "uq_settlement_upgrade"),
    ]:
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes(table)}
        if name not in indexes:
            # Existing duplicates fail migration visibly; never discard real records.
            op.create_index(name, table, [column], unique=True)


def downgrade() -> None:
    # Keep job provenance and integrity constraints; restore backups for rollback.
    pass
