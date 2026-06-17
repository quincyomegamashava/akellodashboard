"""Repair migration: ensure Sales & Marketing stakeholder schema is complete."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import (
    add_column_if_missing,
    boolean_not_null_default,
    create_index_if_missing,
    table_exists,
    timestamp_column_ddl,
)


revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None

LEADS = "sales_marketing_stakeholder_leads"
NOTES = "sales_marketing_stakeholder_lead_notes"


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, LEADS):
        return

    add_column_if_missing(
        bind,
        LEADS,
        "follow_up_status",
        "follow_up_status VARCHAR(32) NOT NULL DEFAULT 'new'",
    )
    add_column_if_missing(
        bind,
        LEADS,
        "duplicate_dismissed",
        boolean_not_null_default(bind, "duplicate_dismissed"),
    )
    add_column_if_missing(bind, LEADS, "lead_score", "lead_score INTEGER")
    add_column_if_missing(
        bind,
        LEADS,
        "score_updated_at",
        timestamp_column_ddl(bind, "score_updated_at"),
    )
    create_index_if_missing(
        bind,
        "ix_sales_marketing_stakeholder_leads_follow_up_status",
        LEADS,
        ["follow_up_status"],
    )

    if not table_exists(bind, NOTES):
        op.create_table(
            NOTES,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["lead_id"], [f"{LEADS}.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sales_marketing_stakeholder_lead_notes_lead_id",
            NOTES,
            ["lead_id"],
        )


def downgrade():
    pass
