"""operational health, maintenance and remote operations

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_availability_intervals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )
    op.create_index(
        "ix_availability_device_started",
        "device_availability_intervals",
        ["device_id", "started_at"],
    )
    op.create_index(
        "ix_availability_device_open",
        "device_availability_intervals",
        ["device_id", "ended_at"],
    )

    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )
    op.create_index(
        "ix_maintenance_device_window",
        "maintenance_windows",
        ["device_id", "starts_at", "ends_at"],
    )

    op.add_column(
        "alerts",
        sa.Column("maintenance_window_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_alerts_maintenance_window",
        "alerts",
        "maintenance_windows",
        ["maintenance_window_id"],
        ["id"],
    )

    op.create_table(
        "remote_operations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("agent_id", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )
    op.create_index(
        "ix_remote_operations_agent_status_created",
        "remote_operations",
        ["agent_id", "status", "created_at"],
    )
    op.create_index(
        "ix_remote_operations_device_created",
        "remote_operations",
        ["device_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_remote_operations_device_created", table_name="remote_operations")
    op.drop_index("ix_remote_operations_agent_status_created", table_name="remote_operations")
    op.drop_table("remote_operations")
    op.drop_constraint("fk_alerts_maintenance_window", "alerts", type_="foreignkey")
    op.drop_column("alerts", "maintenance_window_id")
    op.drop_index("ix_maintenance_device_window", table_name="maintenance_windows")
    op.drop_table("maintenance_windows")
    op.drop_index("ix_availability_device_open", table_name="device_availability_intervals")
    op.drop_index("ix_availability_device_started", table_name="device_availability_intervals")
    op.drop_table("device_availability_intervals")
