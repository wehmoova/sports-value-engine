"""Durable historical checkpoints and versioned training/validation evidence."""

import sqlalchemy as sa

from alembic import op

revision = "0004_research"
down_revision = "0003_cloud_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy 0001 imports current metadata; keep fresh-install compatibility.
    if "research_artifacts" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "research_artifacts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("artifact_key", sa.String(180), nullable=False),
            sa.Column("sport", sa.String(40), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.UniqueConstraint("kind", "artifact_key", name="research_artifact_key"),
        )
        op.create_index("ix_research_artifacts_kind", "research_artifacts", ["kind"])
        op.create_index("ix_research_artifacts_sport", "research_artifacts", ["sport"])


def downgrade() -> None:
    op.drop_table("research_artifacts")
