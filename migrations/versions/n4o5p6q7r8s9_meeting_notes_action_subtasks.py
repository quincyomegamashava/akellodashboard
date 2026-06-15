"""Add meeting_notes_action_subtasks table."""

from alembic import op
import sqlalchemy as sa


revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if _table_exists("meeting_notes_action_subtasks"):
        return
    op.create_table(
        "meeting_notes_action_subtasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_item_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["action_item_id"],
            ["meeting_notes_action_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_notes_action_subtasks_action_item_id",
        "meeting_notes_action_subtasks",
        ["action_item_id"],
    )


def downgrade():
    if not _table_exists("meeting_notes_action_subtasks"):
        return
    op.drop_index(
        "ix_meeting_notes_action_subtasks_action_item_id",
        table_name="meeting_notes_action_subtasks",
    )
    op.drop_table("meeting_notes_action_subtasks")
