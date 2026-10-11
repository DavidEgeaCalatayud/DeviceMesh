"""persistent network interface inventory snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "network_interface_inventory",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("interface_name", sa.String(length=128), nullable=False),
        sa.Column("mac_address", sa.String(length=64), nullable=True),
        sa.Column("operational_status", sa.String(length=16), nullable=False),
        sa.Column("mtu", sa.Integer(), nullable=True),
        sa.Column("speed_bps", sa.BigInteger(), nullable=True),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("ip_addresses", sa.JSON(), nullable=False),
        sa.Column("gateways", sa.JSON(), nullable=False),
        sa.Column("dns_servers", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "interface_name", name="uq_network_interface_device_name"),
    )
    op.create_index(
        "ix_network_interface_inventory_device_present",
        "network_interface_inventory",
        ["device_id", "present"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_network_interface_inventory_device_present",
        table_name="network_interface_inventory",
    )
    op.drop_table("network_interface_inventory")
