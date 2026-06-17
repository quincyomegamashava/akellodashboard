"""Sales marketing: lead status, notes, duplicate dismiss."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import (
    add_column_if_missing,
    boolean_not_null_default,
    create_index_if_missing,
    table_exists,
)


revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if table_exists(bind, "sales_marketing_stakeholder_leads"):
        add_column_if_missing(
            bind,
            "sales_marketing_stakeholder_leads",
            "follow_up_status",
            "follow_up_status VARCHAR(32) NOT NULL DEFAULT 'new'",
        )
        add_column_if_missing(
            bind,
            "sales_marketing_stakeholder_leads",
            "duplicate_dismissed",
            boolean_not_null_default(bind, "duplicate_dismissed"),
        )
        create_index_if_missing(
            bind,
            "ix_sales_marketing_stakeholder_leads_follow_up_status",
            "sales_marketing_stakeholder_leads",
            ["follow_up_status"],
        )

    if not table_exists(bind, "sales_marketing_stakeholder_lead_notes"):
        op.create_table(
            "sales_marketing_stakeholder_lead_notes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], ["sales_marketing_stakeholder_leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sales_marketing_stakeholder_lead_notes_lead_id",
            "sales_marketing_stakeholder_lead_notes",
            ["lead_id"],
        )


def downgrade():
    bind = _bind()
    if table_exists(bind, "sales_marketing_stakeholder_lead_notes"):
        op.drop_table("sales_marketing_stakeholder_lead_notes")
    if table_exists(bind, "sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            batch_op.drop_index("ix_sales_marketing_stakeholder_leads_follow_up_status")
            batch_op.drop_column("duplicate_dismissed")
            batch_op.drop_column("follow_up_status")
