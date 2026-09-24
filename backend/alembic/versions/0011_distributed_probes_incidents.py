"""distributed probes and service incidents

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "synthetic_monitors",
        sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "synthetic_monitors",
        sa.Column("recovery_threshold", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "synthetic_check_results",
        sa.Column("probe_location", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "synthetic_check_results",
        sa.Column("work_id", sa.String(length=36), nullable=True),
    )
    op.create_unique_constraint(
        "uq_synthetic_results_work_id",
        "synthetic_check_results",
        ["work_id"],
    )

    op.create_table(
        "synthetic_probes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_synthetic_probes_last_seen",
        "synthetic_probes",
        ["enabled", "last_seen_at"],
    )

    op.create_table(
        "synthetic_probe_assignments",
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "probe_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_probes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_synthetic_probe_assignments_due",
        "synthetic_probe_assignments",
        ["probe_id", "enabled", "next_run_at"],
    )

    op.create_table(
        "synthetic_probe_work",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "probe_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_probes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
    )
    op.create_index(
        "ix_synthetic_probe_work_probe_status",
        "synthetic_probe_work",
        ["probe_id", "status", "lease_expires_at"],
    )

    op.create_table(
        "service_incident_state",
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("failure_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recovery_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_classification", sa.String(length=32), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "service_incidents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_threshold", sa.Integer(), nullable=False),
        sa.Column("recovery_threshold", sa.Integer(), nullable=False),
        sa.Column("maintenance_active_at_open", sa.Boolean(), nullable=False),
        sa.Column("host_offline_at_open", sa.Boolean(), nullable=False),
        sa.Column("failing_probes", sa.Integer(), nullable=False),
        sa.Column("total_probes", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_service_incidents_monitor_time",
        "service_incidents",
        ["monitor_id", "opened_at"],
    )
    op.create_index(
        "ix_service_incidents_open",
        "service_incidents",
        ["monitor_id", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_incidents_open", table_name="service_incidents")
    op.drop_index("ix_service_incidents_monitor_time", table_name="service_incidents")
    op.drop_table("service_incidents")
    op.drop_table("service_incident_state")
    op.drop_index("ix_synthetic_probe_work_probe_status", table_name="synthetic_probe_work")
    op.drop_table("synthetic_probe_work")
    op.drop_index(
        "ix_synthetic_probe_assignments_due",
        table_name="synthetic_probe_assignments",
    )
    op.drop_table("synthetic_probe_assignments")
    op.drop_index("ix_synthetic_probes_last_seen", table_name="synthetic_probes")
    op.drop_table("synthetic_probes")
    op.drop_constraint(
        "uq_synthetic_results_work_id",
        "synthetic_check_results",
        type_="unique",
    )
    op.drop_column("synthetic_check_results", "work_id")
    op.drop_column("synthetic_check_results", "probe_location")
    op.drop_column("synthetic_monitors", "recovery_threshold")
    op.drop_column("synthetic_monitors", "failure_threshold")
