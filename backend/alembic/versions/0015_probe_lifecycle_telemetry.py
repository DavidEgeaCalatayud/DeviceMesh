"""add distributed-probe credential expiry and runtime telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "synthetic_probes",
        sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE synthetic_probes "
        "SET credential_expires_at = CURRENT_TIMESTAMP + INTERVAL '90 days' "
        "WHERE credential_expires_at IS NULL"
    )
    op.alter_column("synthetic_probes", "credential_expires_at", nullable=False)
    op.add_column("synthetic_probes", sa.Column("agent_version", sa.String(length=32), nullable=True))
    op.add_column("synthetic_probes", sa.Column("uptime_seconds", sa.Integer(), nullable=True))
    op.add_column("synthetic_probes", sa.Column("queue_depth", sa.Integer(), nullable=True))
    op.add_column("synthetic_probes", sa.Column("queue_capacity", sa.Integer(), nullable=True))
    op.add_column(
        "synthetic_probes",
        sa.Column("max_concurrent_checks", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("synthetic_probes", "max_concurrent_checks")
    op.drop_column("synthetic_probes", "queue_capacity")
    op.drop_column("synthetic_probes", "queue_depth")
    op.drop_column("synthetic_probes", "uptime_seconds")
    op.drop_column("synthetic_probes", "agent_version")
    op.drop_column("synthetic_probes", "credential_expires_at")
