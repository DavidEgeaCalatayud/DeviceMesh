"""encrypted mobile push subscriptions."""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_push_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column("token_ciphertext", sa.String(length=8192), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "installation_id",
            name="uq_mobile_push_user_provider_installation",
        ),
        sa.CheckConstraint(
            "provider IN ('fcm', 'apns')",
            name="ck_mobile_push_provider",
        ),
        sa.CheckConstraint(
            "environment IN ('production', 'sandbox')",
            name="ck_mobile_push_environment",
        ),
    )
    op.create_index(
        "ix_mobile_push_user_enabled",
        "mobile_push_subscriptions",
        ["user_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_push_user_enabled", table_name="mobile_push_subscriptions")
    op.drop_table("mobile_push_subscriptions")
