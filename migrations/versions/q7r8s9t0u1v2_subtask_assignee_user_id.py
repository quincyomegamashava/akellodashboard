"""Add assignee_user_id to meeting action subtasks."""

from alembic import op
import sqlalchemy as sa


revision = "q7r8s9t0u1v2"
down_revision = "88a51ab2a25e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("meeting_notes_action_subtasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("assignee_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_meeting_notes_action_subtasks_assignee_user_id",
            "user",
            ["assignee_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_meeting_notes_action_subtasks_assignee_user_id",
            ["assignee_user_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("meeting_notes_action_subtasks", schema=None) as batch_op:
        batch_op.drop_index("ix_meeting_notes_action_subtasks_assignee_user_id")
        batch_op.drop_constraint(
            "fk_meeting_notes_action_subtasks_assignee_user_id", type_="foreignkey"
        )
        batch_op.drop_column("assignee_user_id")
