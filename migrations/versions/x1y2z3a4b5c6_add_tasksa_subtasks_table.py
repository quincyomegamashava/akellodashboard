"""Add tasksa_subtasks table for project management sub-tasks."""

from alembic import op
import sqlalchemy as sa


revision = "x1y2z3a4b5c6"
down_revision = "w5x6y7z8a9b0"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if _table_exists("tasksa_subtasks"):
        return
    op.create_table(
        "tasksa_subtasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tasksa_subtasks_task_id",
        "tasksa_subtasks",
        ["task_id"],
    )


def downgrade():
    if not _table_exists("tasksa_subtasks"):
        return
    op.drop_index("ix_tasksa_subtasks_task_id", table_name="tasksa_subtasks")
    op.drop_table("tasksa_subtasks")
