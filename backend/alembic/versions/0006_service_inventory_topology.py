"""service inventory and observed network topology

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_observations",
        sa.Column("network_cidr", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_device_observations_network_time",
        "device_observations",
        ["network_cidr", "observed_at"],
    )
    op.create_table(
        "device_services",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("transport", sa.String(16), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(128), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("network_cidr", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "device_id",
            "transport",
            "port",
            name="uq_device_service_endpoint",
        ),
    )
    op.create_index(
        "ix_device_services_state_device",
        "device_services",
        ["state", "device_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_services_state_device", table_name="device_services")
    op.drop_table("device_services")
    op.drop_index(
        "ix_device_observations_network_time",
        table_name="device_observations",
    )
    op.drop_column("device_observations", "network_cidr")
