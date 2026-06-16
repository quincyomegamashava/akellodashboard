"""Phases 1-3: decisions, event slugs, carry-forward, cross-links, lead scoring."""

from alembic import op
import sqlalchemy as sa


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if not _table_exists("meeting_notes_decisions"):
        op.create_table(
            "meeting_notes_decisions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_note_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_excerpt", sa.Text(), nullable=True),
            sa.Column("decided_at", sa.Date(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["meeting_note_id"], ["meeting_notes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_mn_decisions_meeting_id", "meeting_notes_decisions", ["meeting_note_id"])

    if _table_exists("sales_marketing_events"):
        with op.batch_alter_table("sales_marketing_events", schema=None) as batch_op:
            batch_op.add_column(sa.Column("slug", sa.String(length=120), nullable=True))
            batch_op.add_column(sa.Column("banner_text", sa.Text(), nullable=True))
            batch_op.add_column(sa.Column("cost_estimate", sa.Numeric(12, 2), nullable=True))
            batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
            batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
        op.create_index("ix_sm_events_slug", "sales_marketing_events", ["slug"], unique=True)

    if _table_exists("meeting_notes_action_items"):
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("carry_forward_count", sa.Integer(), nullable=False, server_default="0")
            )
            batch_op.add_column(sa.Column("stakeholder_lead_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("marketing_event_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_mn_action_stakeholder_lead",
                "sales_marketing_stakeholder_leads",
                ["stakeholder_lead_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_mn_action_marketing_event",
                "sales_marketing_events",
                ["marketing_event_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if _table_exists("sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            batch_op.add_column(sa.Column("lead_score", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("score_updated_at", sa.DateTime(), nullable=True))

    if not _table_exists("sales_marketing_email_templates"):
        op.create_table(
            "sales_marketing_email_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("subject", sa.String(length=500), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade():
    op.drop_table("sales_marketing_email_templates")
    if _table_exists("sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            batch_op.drop_column("score_updated_at")
            batch_op.drop_column("lead_score")
    if _table_exists("meeting_notes_action_items"):
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            batch_op.drop_constraint("fk_mn_action_marketing_event", type_="foreignkey")
            batch_op.drop_constraint("fk_mn_action_stakeholder_lead", type_="foreignkey")
            batch_op.drop_column("marketing_event_id")
            batch_op.drop_column("stakeholder_lead_id")
            batch_op.drop_column("carry_forward_count")
    if _table_exists("sales_marketing_events"):
        op.drop_index("ix_sm_events_slug", table_name="sales_marketing_events")
        with op.batch_alter_table("sales_marketing_events", schema=None) as batch_op:
            batch_op.drop_column("longitude")
            batch_op.drop_column("latitude")
            batch_op.drop_column("cost_estimate")
            batch_op.drop_column("banner_text")
            batch_op.drop_column("slug")
    op.drop_table("meeting_notes_decisions")
