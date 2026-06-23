"""Add sub-task assignees, start_date, and end_date for project management."""

from alembic import op
import sqlalchemy as sa


revision = "y2z3a4b5c6d7"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _column_exists(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade():
    if _table_exists("tasksa_subtasks"):
        if not _column_exists("tasksa_subtasks", "start_date"):
            op.add_column("tasksa_subtasks", sa.Column("start_date", sa.DateTime(), nullable=True))
        if not _column_exists("tasksa_subtasks", "end_date"):
            op.add_column("tasksa_subtasks", sa.Column("end_date", sa.DateTime(), nullable=True))

    if not _table_exists("taskasubtask_assigneesa"):
        op.create_table(
            "taskasubtask_assigneesa",
            sa.Column("subtask_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["subtask_id"], ["tasksa_subtasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("subtask_id", "user_id"),
        )


def downgrade():
    if _table_exists("taskasubtask_assigneesa"):
        op.drop_table("taskasubtask_assigneesa")
    if _table_exists("tasksa_subtasks"):
        if _column_exists("tasksa_subtasks", "end_date"):
            op.drop_column("tasksa_subtasks", "end_date")
        if _column_exists("tasksa_subtasks", "start_date"):
            op.drop_column("tasksa_subtasks", "start_date")
