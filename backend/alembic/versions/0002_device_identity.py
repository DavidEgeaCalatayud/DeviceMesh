"""device identity and observation history"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("operating_system_version", sa.String(255)))
    op.add_column("devices", sa.Column("architecture", sa.String(64)))
    op.add_column("devices", sa.Column("manufacturer", sa.String(255)))

    op.create_table(
        "device_interfaces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("interface_name", sa.String(128)),
        sa.Column("mac_address", sa.String(64)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_interfaces_device", "device_interfaces", ["device_id"])
    op.create_index("ix_device_interfaces_mac", "device_interfaces", ["mac_address"])
    op.create_index("ix_device_interfaces_ip", "device_interfaces", ["ip_address"])

    op.create_table(
        "device_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hostname", sa.String(255)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("mac_address", sa.String(64)),
        sa.Column("manufacturer", sa.String(255)),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_index(
        "ix_device_observations_device_time",
        "device_observations",
        ["device_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_observations_device_time", table_name="device_observations")
    op.drop_table("device_observations")
    op.drop_index("ix_device_interfaces_ip", table_name="device_interfaces")
    op.drop_index("ix_device_interfaces_mac", table_name="device_interfaces")
    op.drop_index("ix_device_interfaces_device", table_name="device_interfaces")
    op.drop_table("device_interfaces")
    op.drop_column("devices", "manufacturer")
    op.drop_column("devices", "architecture")
    op.drop_column("devices", "operating_system_version")
