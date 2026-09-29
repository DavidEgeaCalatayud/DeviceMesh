"""synthetic HTTP headers, secret references and body assertions."""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synthetic_http_settings",
        sa.Column(
            "monitor_id",
            sa.String(length=36),
            sa.ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("secret_headers", sa.JSON(), nullable=False),
        sa.Column("expected_body_contains", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("synthetic_http_settings")
