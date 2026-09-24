"""synthetic service monitoring

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synthetic_monitors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("monitor_type", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=2048), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("expected_status_min", sa.Integer(), nullable=True),
        sa.Column("expected_status_max", sa.Integer(), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )
    op.create_index(
        "ix_synthetic_monitors_device_enabled",
        "synthetic_monitors",
        ["device_id", "enabled"],
    )

    op.create_table(
        "synthetic_probe_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("monitor_id", sa.String(length=36), nullable=False),
        sa.Column("probe_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id"], ["synthetic_monitors.id"]),
    )
    op.create_index(
        "ix_synthetic_results_monitor_observed",
        "synthetic_probe_results",
        ["monitor_id", "observed_at"],
    )
    op.create_index(
        "ix_synthetic_results_probe_observed",
        "synthetic_probe_results",
        ["probe_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_synthetic_results_probe_observed",
        table_name="synthetic_probe_results",
    )
    op.drop_index(
        "ix_synthetic_results_monitor_observed",
        table_name="synthetic_probe_results",
    )
    op.drop_table("synthetic_probe_results")
    op.drop_index("ix_synthetic_monitors_device_enabled", table_name="synthetic_monitors")
    op.drop_table("synthetic_monitors")
