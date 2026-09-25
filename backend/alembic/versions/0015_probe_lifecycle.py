"""add distributed-probe credential lifecycle and operational telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synthetic_probe_lifecycle",
        sa.Column("probe_id", sa.String(length=36), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_version", sa.String(length=64), nullable=True),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=True),
        sa.Column("outbox_depth", sa.Integer(), nullable=True),
        sa.Column("failed_requests_total", sa.BigInteger(), nullable=True),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        sa.Column("telemetry_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["probe_id"], ["synthetic_probes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("probe_id"),
    )
    # Existing probe credentials gain a finite migration window rather than
    # remaining valid indefinitely. New/rotated credentials use configured TTL.
    op.execute(
        sa.text(
            "INSERT INTO synthetic_probe_lifecycle (probe_id, token_expires_at) "
            "SELECT id, CURRENT_TIMESTAMP + INTERVAL '90 days' FROM synthetic_probes"
        )
    )


def downgrade() -> None:
    op.drop_table("synthetic_probe_lifecycle")
