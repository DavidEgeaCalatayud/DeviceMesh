"""add distributed-probe credential lifecycle and runtime telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synthetic_probe_credentials",
        sa.Column("probe_id", sa.String(length=36), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["probe_id"], ["synthetic_probes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("probe_id"),
    )
    op.create_table(
        "synthetic_probe_runtime",
        sa.Column("probe_id", sa.String(length=36), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("uptime_seconds", sa.Integer(), nullable=False),
        sa.Column("queue_depth", sa.Integer(), nullable=False),
        sa.Column("queue_capacity", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_checks", sa.Integer(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["probe_id"], ["synthetic_probes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("probe_id"),
        sa.CheckConstraint("uptime_seconds >= 0", name="ck_probe_runtime_uptime_nonnegative"),
        sa.CheckConstraint("queue_depth >= 0", name="ck_probe_runtime_queue_depth_nonnegative"),
        sa.CheckConstraint("queue_capacity > 0", name="ck_probe_runtime_queue_capacity_positive"),
        sa.CheckConstraint("queue_depth <= queue_capacity", name="ck_probe_runtime_queue_within_capacity"),
        sa.CheckConstraint("max_concurrent_checks > 0", name="ck_probe_runtime_concurrency_positive"),
    )

    op.execute(
        "INSERT INTO synthetic_probe_credentials (probe_id, rotated_at, expires_at) "
        "SELECT id, updated_at, CURRENT_TIMESTAMP + INTERVAL '90 days' FROM synthetic_probes"
    )
    op.execute(
        """
        CREATE FUNCTION devicemesh_probe_credential_lifecycle() RETURNS trigger AS $$
        BEGIN
            INSERT INTO synthetic_probe_credentials (probe_id, rotated_at, expires_at)
            VALUES (NEW.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '90 days')
            ON CONFLICT (probe_id) DO UPDATE
            SET rotated_at = EXCLUDED.rotated_at,
                expires_at = EXCLUDED.expires_at;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_devicemesh_probe_credential_lifecycle
        AFTER INSERT OR UPDATE OF token_hash ON synthetic_probes
        FOR EACH ROW EXECUTE FUNCTION devicemesh_probe_credential_lifecycle()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_devicemesh_probe_credential_lifecycle ON synthetic_probes"
    )
    op.execute("DROP FUNCTION IF EXISTS devicemesh_probe_credential_lifecycle()")
    op.drop_table("synthetic_probe_runtime")
    op.drop_table("synthetic_probe_credentials")
