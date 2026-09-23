"""metric history query index

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_metric_samples_device_metric_timestamp",
        "metric_samples",
        ["device_id", "metric_type", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_metric_samples_device_metric_timestamp", table_name="metric_samples")
