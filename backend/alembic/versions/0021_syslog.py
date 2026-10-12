"""bounded persistent syslog ingestion and search."""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "syslog_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_address", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("facility", sa.Integer(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("app_name", sa.String(length=128), nullable=True),
        sa.Column("proc_id", sa.String(length=64), nullable=True),
        sa.Column("msg_id", sa.String(length=64), nullable=True),
        sa.Column("message", sa.String(length=4096), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.CheckConstraint("facility BETWEEN 0 AND 23", name="ck_syslog_facility"),
        sa.CheckConstraint("severity BETWEEN 0 AND 7", name="ck_syslog_severity"),
    )
    op.create_index("ix_syslog_received_at", "syslog_messages", ["received_at"])
    op.create_index("ix_syslog_source_address", "syslog_messages", ["source_address"])
    op.create_index("ix_syslog_device_id", "syslog_messages", ["device_id"])
    op.create_index("ix_syslog_facility", "syslog_messages", ["facility"])
    op.create_index("ix_syslog_severity", "syslog_messages", ["severity"])
    op.create_index("ix_syslog_hostname", "syslog_messages", ["hostname"])
    op.create_index("ix_syslog_device_time", "syslog_messages", ["device_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_syslog_device_time", table_name="syslog_messages")
    op.drop_index("ix_syslog_hostname", table_name="syslog_messages")
    op.drop_index("ix_syslog_severity", table_name="syslog_messages")
    op.drop_index("ix_syslog_facility", table_name="syslog_messages")
    op.drop_index("ix_syslog_device_id", table_name="syslog_messages")
    op.drop_index("ix_syslog_source_address", table_name="syslog_messages")
    op.drop_index("ix_syslog_received_at", table_name="syslog_messages")
    op.drop_table("syslog_messages")
