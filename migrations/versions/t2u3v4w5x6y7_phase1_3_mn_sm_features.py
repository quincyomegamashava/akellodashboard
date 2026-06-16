from alembic import op
import sqlalchemy as sa

from app.migration_schema import (
    add_column_if_missing,
    column_exists,
    create_index_if_missing,
    fk_exists,
    index_exists,
    table_exists,
)


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()

    if not table_exists(bind, "meeting_notes_decisions"):
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
    elif not index_exists(bind, "meeting_notes_decisions", "ix_mn_decisions_meeting_id"):
        op.create_index("ix_mn_decisions_meeting_id", "meeting_notes_decisions", ["meeting_note_id"])

    if table_exists(bind, "sales_marketing_events"):
        add_column_if_missing(bind, "sales_marketing_events", "slug", "slug VARCHAR(120)")
        add_column_if_missing(bind, "sales_marketing_events", "banner_text", "banner_text TEXT")
        add_column_if_missing(
            bind, "sales_marketing_events", "cost_estimate", "cost_estimate NUMERIC(12, 2)"
        )
        add_column_if_missing(bind, "sales_marketing_events", "latitude", "latitude FLOAT")
        add_column_if_missing(bind, "sales_marketing_events", "longitude", "longitude FLOAT")
        create_index_if_missing(
            bind, "ix_sm_events_slug", "sales_marketing_events", ["slug"], unique=True
        )

    if table_exists(bind, "meeting_notes_action_items"):
        add_column_if_missing(
            bind,
            "meeting_notes_action_items",
            "carry_forward_count",
            "carry_forward_count INTEGER NOT NULL DEFAULT 0",
        )
        add_column_if_missing(
            bind, "meeting_notes_action_items", "stakeholder_lead_id", "stakeholder_lead_id INTEGER"
        )
        add_column_if_missing(
            bind, "meeting_notes_action_items", "marketing_event_id", "marketing_event_id INTEGER"
        )
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            if column_exists(bind, "meeting_notes_action_items", "stakeholder_lead_id") and not fk_exists(
                bind, "meeting_notes_action_items", "fk_mn_action_stakeholder_lead"
            ):
                batch_op.create_foreign_key(
                    "fk_mn_action_stakeholder_lead",
                    "sales_marketing_stakeholder_leads",
                    ["stakeholder_lead_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if column_exists(bind, "meeting_notes_action_items", "marketing_event_id") and not fk_exists(
                bind, "meeting_notes_action_items", "fk_mn_action_marketing_event"
            ):
                batch_op.create_foreign_key(
                    "fk_mn_action_marketing_event",
                    "sales_marketing_events",
                    ["marketing_event_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    if table_exists(bind, "sales_marketing_stakeholder_leads"):
        add_column_if_missing(bind, "sales_marketing_stakeholder_leads", "lead_score", "lead_score INTEGER")
        add_column_if_missing(
            bind, "sales_marketing_stakeholder_leads", "score_updated_at", "score_updated_at DATETIME"
        )

    if not table_exists(bind, "sales_marketing_email_templates"):
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
    bind = _bind()
    if table_exists(bind, "sales_marketing_email_templates"):
        op.drop_table("sales_marketing_email_templates")
    if table_exists(bind, "sales_marketing_stakeholder_leads"):
        with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
            if column_exists(bind, "sales_marketing_stakeholder_leads", "score_updated_at"):
                batch_op.drop_column("score_updated_at")
            if column_exists(bind, "sales_marketing_stakeholder_leads", "lead_score"):
                batch_op.drop_column("lead_score")
    if table_exists(bind, "meeting_notes_action_items"):
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            if fk_exists(bind, "meeting_notes_action_items", "fk_mn_action_marketing_event"):
                batch_op.drop_constraint("fk_mn_action_marketing_event", type_="foreignkey")
            if fk_exists(bind, "meeting_notes_action_items", "fk_mn_action_stakeholder_lead"):
                batch_op.drop_constraint("fk_mn_action_stakeholder_lead", type_="foreignkey")
            if column_exists(bind, "meeting_notes_action_items", "marketing_event_id"):
                batch_op.drop_column("marketing_event_id")
            if column_exists(bind, "meeting_notes_action_items", "stakeholder_lead_id"):
                batch_op.drop_column("stakeholder_lead_id")
            if column_exists(bind, "meeting_notes_action_items", "carry_forward_count"):
                batch_op.drop_column("carry_forward_count")
    if table_exists(bind, "sales_marketing_events"):
        if index_exists(bind, "sales_marketing_events", "ix_sm_events_slug"):
            op.drop_index("ix_sm_events_slug", table_name="sales_marketing_events")
        with op.batch_alter_table("sales_marketing_events", schema=None) as batch_op:
            for col in ("longitude", "latitude", "cost_estimate", "banner_text", "slug"):
                if column_exists(bind, "sales_marketing_events", col):
                    batch_op.drop_column(col)
    if table_exists(bind, "meeting_notes_decisions"):
        op.drop_table("meeting_notes_decisions")
