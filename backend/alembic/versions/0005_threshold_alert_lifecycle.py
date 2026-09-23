"""threshold alert lifecycle state

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "alert_condition_states",
        sa.Column("rule_id", sa.BigInteger(), sa.ForeignKey("alert_rules.id"), primary_key=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), primary_key=True),
        sa.Column("first_triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_value", sa.Float(), nullable=False),
    )
    op.create_index(
        "uq_alerts_active_rule_device",
        "alerts",
        ["rule_id", "device_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    op.create_index(
        "ix_alerts_device_opened_at",
        "alerts",
        ["device_id", "opened_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_device_opened_at", table_name="alerts")
    op.drop_index("uq_alerts_active_rule_device", table_name="alerts")
    op.drop_table("alert_condition_states")
    op.drop_column("alert_rules", "enabled")
