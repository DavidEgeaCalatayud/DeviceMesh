"""complete service platform and SRE workflow primitives."""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_groups_name"), "service_groups", ["name"], unique=False)
    op.create_table(
        "service_group_members",
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["service_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["service_catalog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "service_id"),
    )
    op.create_table(
        "service_dependencies",
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("depends_on_service_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["depends_on_service_id"], ["service_catalog.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["service_catalog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("service_id", "depends_on_service_id"),
        sa.CheckConstraint("service_id <> depends_on_service_id", name="ck_service_dependency_not_self"),
    )
    op.add_column("incident_management", sa.Column("impact_summary", sa.String(length=10000), nullable=False, server_default=""))
    op.add_column("incident_management", sa.Column("postmortem", sa.String(length=20000), nullable=False, server_default=""))
    op.add_column("service_slos", sa.Column("sli_mode", sa.String(length=16), nullable=False, server_default="checks"))
    op.create_check_constraint("ck_service_slo_sli_mode", "service_slos", "sli_mode IN ('checks', 'time')")


def downgrade() -> None:
    op.drop_constraint("ck_service_slo_sli_mode", "service_slos", type_="check")
    op.drop_column("service_slos", "sli_mode")
    op.drop_column("incident_management", "postmortem")
    op.drop_column("incident_management", "impact_summary")
    op.drop_table("service_dependencies")
    op.drop_table("service_group_members")
    op.drop_index(op.f("ix_service_groups_name"), table_name="service_groups")
    op.drop_table("service_groups")
