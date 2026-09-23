"""secure agent enrollment and credentials

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_enrollment_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(128), nullable=False),
    )
    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("credential_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("rotated_from_id", sa.String(36)),
    )
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])
    op.create_table(
        "agent_request_nonces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("credential_id", sa.String(36), sa.ForeignKey("agent_credentials.id"), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("credential_id", "nonce", name="uq_agent_request_nonce"),
    )
    op.create_index("ix_agent_request_nonces_seen_at", "agent_request_nonces", ["seen_at"])
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(128)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_security_audit_events_time", "security_audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_events_time", table_name="security_audit_events")
    op.drop_table("security_audit_events")
    op.drop_index("ix_agent_request_nonces_seen_at", table_name="agent_request_nonces")
    op.drop_table("agent_request_nonces")
    op.drop_index("ix_agent_credentials_agent_id", table_name="agent_credentials")
    op.drop_table("agent_credentials")
    op.drop_table("agent_enrollment_tokens")
