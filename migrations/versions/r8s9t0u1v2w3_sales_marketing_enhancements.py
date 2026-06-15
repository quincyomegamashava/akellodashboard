"""Sales marketing: lead status, notes, duplicate dismiss."""

from alembic import op
import sqlalchemy as sa


revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if _table_exists("sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("follow_up_status", sa.String(length=32), nullable=False, server_default="new")
            )
            batch_op.add_column(
                sa.Column(
                    "duplicate_dismissed",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        op.create_index(
            "ix_sales_marketing_stakeholder_leads_follow_up_status",
            "sales_marketing_stakeholder_leads",
            ["follow_up_status"],
        )

    if not _table_exists("sales_marketing_stakeholder_lead_notes"):
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
    if _table_exists("sales_marketing_stakeholder_lead_notes"):
        op.drop_table("sales_marketing_stakeholder_lead_notes")
    if _table_exists("sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            batch_op.drop_index("ix_sales_marketing_stakeholder_leads_follow_up_status")
            batch_op.drop_column("duplicate_dismissed")
            batch_op.drop_column("follow_up_status")
