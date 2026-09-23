"""initial DeviceMesh schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("devices", sa.Column("id", sa.String(128), primary_key=True), sa.Column("hostname", sa.String(255)), sa.Column("operating_system", sa.String(255)), sa.Column("status", sa.String(32), nullable=False, server_default="unknown"), sa.Column("first_seen", sa.DateTime(timezone=True)), sa.Column("last_seen", sa.DateTime(timezone=True)))
    op.create_table("agents", sa.Column("id", sa.String(128), primary_key=True), sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False), sa.Column("last_seen", sa.DateTime(timezone=True)))
    op.create_table("metric_samples", sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False), sa.Column("metric_type", sa.String(128), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("value", sa.Float(), nullable=False), sa.Column("unit", sa.String(32)))
    op.create_index("ix_metric_samples_device_time", "metric_samples", ["device_id", "timestamp"])
    op.create_table("device_events", sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False), sa.Column("name", sa.String(128), nullable=False), sa.Column("severity", sa.String(32), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table("alert_rules", sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), sa.Column("metric_name", sa.String(128), nullable=False), sa.Column("operator", sa.String(4), nullable=False), sa.Column("threshold", sa.Float(), nullable=False), sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("alerts", sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True), sa.Column("rule_id", sa.BigInteger(), sa.ForeignKey("alert_rules.id"), nullable=False), sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False), sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False), sa.Column("closed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_table("alerts"); op.drop_table("alert_rules"); op.drop_table("device_events"); op.drop_index("ix_metric_samples_device_time", table_name="metric_samples"); op.drop_table("metric_samples"); op.drop_table("agents"); op.drop_table("devices")
