"""synthetic monitoring

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "synthetic_monitors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=2048), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("http_method", sa.String(length=8), nullable=True),
        sa.Column("expected_status", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_synthetic_monitors_due",
        "synthetic_monitors",
        ["enabled", "next_run_at"],
    )
    op.create_table(
        "synthetic_check_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_kind", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.Column("probe_id", sa.String(length=128), nullable=False),
    )
    op.create_index(
        "ix_synthetic_results_monitor_time",
        "synthetic_check_results",
        ["monitor_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_synthetic_results_monitor_time", table_name="synthetic_check_results")
    op.drop_table("synthetic_check_results")
    op.drop_index("ix_synthetic_monitors_due", table_name="synthetic_monitors")
    op.drop_table("synthetic_monitors")
