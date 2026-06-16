from alembic import op
import sqlalchemy as sa

from app.migration_schema import (
    column_exists,
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


def _table_exists(name):
    return table_exists(_bind(), name)


def _column_exists(table_name, column_name):
    return column_exists(_bind(), table_name, column_name)


def _index_exists(table_name, index_name):
    return index_exists(_bind(), table_name, index_name)


def _fk_exists(table_name, fk_name):
    return fk_exists(_bind(), table_name, fk_name)


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
    elif not _index_exists("meeting_notes_decisions", "ix_mn_decisions_meeting_id"):
        op.create_index("ix_mn_decisions_meeting_id", "meeting_notes_decisions", ["meeting_note_id"])

    if _table_exists("sales_marketing_events"):
        event_columns = (
            ("slug", sa.Column("slug", sa.String(length=120), nullable=True)),
            ("banner_text", sa.Column("banner_text", sa.Text(), nullable=True)),
            ("cost_estimate", sa.Column("cost_estimate", sa.Numeric(12, 2), nullable=True)),
            ("latitude", sa.Column("latitude", sa.Float(), nullable=True)),
            ("longitude", sa.Column("longitude", sa.Float(), nullable=True)),
        )
        missing_event_columns = [
            column for name, column in event_columns if not _column_exists("sales_marketing_events", name)
        ]
        if missing_event_columns:
            with op.batch_alter_table("sales_marketing_events", schema=None) as batch_op:
                for column in missing_event_columns:
                    batch_op.add_column(column)
        if not _index_exists("sales_marketing_events", "ix_sm_events_slug"):
            op.create_index("ix_sm_events_slug", "sales_marketing_events", ["slug"], unique=True)

    if _table_exists("meeting_notes_action_items"):
        action_columns = (
            (
                "carry_forward_count",
                sa.Column("carry_forward_count", sa.Integer(), nullable=False, server_default="0"),
            ),
            ("stakeholder_lead_id", sa.Column("stakeholder_lead_id", sa.Integer(), nullable=True)),
            ("marketing_event_id", sa.Column("marketing_event_id", sa.Integer(), nullable=True)),
        )
        missing_action_columns = [
            column
            for name, column in action_columns
            if not _column_exists("meeting_notes_action_items", name)
        ]
        if missing_action_columns:
            with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
                for column in missing_action_columns:
                    batch_op.add_column(column)
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            if _column_exists("meeting_notes_action_items", "stakeholder_lead_id") and not _fk_exists(
                "meeting_notes_action_items", "fk_mn_action_stakeholder_lead"
            ):
                batch_op.create_foreign_key(
                    "fk_mn_action_stakeholder_lead",
                    "sales_marketing_stakeholder_leads",
                    ["stakeholder_lead_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if _column_exists("meeting_notes_action_items", "marketing_event_id") and not _fk_exists(
                "meeting_notes_action_items", "fk_mn_action_marketing_event"
            ):
                batch_op.create_foreign_key(
                    "fk_mn_action_marketing_event",
                    "sales_marketing_events",
                    ["marketing_event_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    if _table_exists("sales_marketing_stakeholder_leads"):
        lead_columns = (
            ("lead_score", sa.Column("lead_score", sa.Integer(), nullable=True)),
            ("score_updated_at", sa.Column("score_updated_at", sa.DateTime(), nullable=True)),
        )
        missing_lead_columns = [
            column
            for name, column in lead_columns
            if not _column_exists("sales_marketing_stakeholder_leads", name)
        ]
        if missing_lead_columns:
            with op.batch_alter_table("sales_marketing_stakeholder_leads", schema=None) as batch_op:
                for column in missing_lead_columns:
                    batch_op.add_column(column)

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
