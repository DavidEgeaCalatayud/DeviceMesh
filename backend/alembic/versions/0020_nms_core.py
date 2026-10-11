"""SNMPv3 NMS targets, physical neighbors, routes, ARP, VLAN and interface counters."""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "network_management_targets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False, unique=True),
        sa.Column("address", sa.String(length=64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("auth_protocol", sa.String(length=16), nullable=False),
        sa.Column("auth_secret_ref", sa.String(length=128), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=128), nullable=True),
    )
    op.create_table(
        "network_neighbors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("local_interface", sa.String(length=128), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("remote_chassis_id", sa.String(length=255), nullable=True),
        sa.Column("remote_system_name", sa.String(length=255), nullable=True),
        sa.Column("remote_port_id", sa.String(length=255), nullable=True),
        sa.Column("remote_device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "device_id", "local_interface", "protocol", "remote_chassis_id", "remote_port_id",
            name="uq_network_neighbor_link",
        ),
    )
    op.create_index("ix_network_neighbors_device_present", "network_neighbors", ["device_id", "present"])
    op.create_table(
        "network_routes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("destination", sa.String(length=64), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("next_hop", sa.String(length=64), nullable=True),
        sa.Column("interface_name", sa.String(length=128), nullable=True),
        sa.Column("route_type", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "destination", "prefix_length", "next_hop", name="uq_network_route"),
    )
    op.create_table(
        "network_arp_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("interface_name", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("mac_address", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "ip_address", name="uq_network_arp_device_ip"),
    )
    op.create_table(
        "network_vlans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("device_id", "vlan_id", name="uq_network_vlan_device_id"),
    )
    op.create_table(
        "network_interface_counters",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("interface_name", sa.String(length=128), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("in_octets", sa.BigInteger(), nullable=True),
        sa.Column("out_octets", sa.BigInteger(), nullable=True),
        sa.Column("in_errors", sa.BigInteger(), nullable=True),
        sa.Column("out_errors", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_network_interface_counters_device_time",
        "network_interface_counters",
        ["device_id", "sampled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_network_interface_counters_device_time", table_name="network_interface_counters")
    op.drop_table("network_interface_counters")
    op.drop_table("network_vlans")
    op.drop_table("network_arp_entries")
    op.drop_table("network_routes")
    op.drop_index("ix_network_neighbors_device_present", table_name="network_neighbors")
    op.drop_table("network_neighbors")
    op.drop_table("network_management_targets")
