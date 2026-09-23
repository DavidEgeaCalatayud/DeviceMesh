"""event timeline indexes"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_device_events_time", "device_events", ["timestamp"])
    op.create_index(
        "ix_device_events_device_time",
        "device_events",
        ["device_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_events_device_time", table_name="device_events")
    op.drop_index("ix_device_events_time", table_name="device_events")
