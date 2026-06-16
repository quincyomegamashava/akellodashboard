"""Add assignee_user_id to meeting action subtasks."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import add_column_if_missing, create_index_if_missing, table_exists


revision = "q7r8s9t0u1v2"
down_revision = "88a51ab2a25e"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, "meeting_notes_action_subtasks"):
        return

    add_column_if_missing(
        bind,
        "meeting_notes_action_subtasks",
        "assignee_user_id",
        "assignee_user_id INTEGER REFERENCES user(id)",
    )
    create_index_if_missing(
        bind,
        "ix_meeting_notes_action_subtasks_assignee_user_id",
        "meeting_notes_action_subtasks",
        ["assignee_user_id"],
    )


def downgrade():
    bind = _bind()
    if not table_exists(bind, "meeting_notes_action_subtasks"):
        return
    with op.batch_alter_table("meeting_notes_action_subtasks", schema=None) as batch_op:
        batch_op.drop_index("ix_meeting_notes_action_subtasks_assignee_user_id")
        batch_op.drop_column("assignee_user_id")
