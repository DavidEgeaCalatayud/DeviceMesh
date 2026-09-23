"""hourly telemetry rollups

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metric_hourly_rollups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("metric_type", sa.String(length=128), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("average", sa.Float(), nullable=False),
        sa.Column("minimum", sa.Float(), nullable=False),
        sa.Column("maximum", sa.Float(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "metric_type",
            "bucket_start",
            name="uq_metric_hourly_rollup_bucket",
        ),
    )
    op.create_index(
        "ix_metric_hourly_rollups_device_metric_bucket",
        "metric_hourly_rollups",
        ["device_id", "metric_type", "bucket_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metric_hourly_rollups_device_metric_bucket",
        table_name="metric_hourly_rollups",
    )
    op.drop_table("metric_hourly_rollups")
