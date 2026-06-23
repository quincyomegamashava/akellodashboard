"""PM roadmap: comments, activity, labels, priority, notification task_id."""

from alembic import op
import sqlalchemy as sa


revision = "z3a4b5c6d7e8"
down_revision = "y2z3a4b5c6d7"
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
    if not _column_exists("tasksa", "priority"):
        op.add_column("tasksa", sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"))
        op.create_index("ix_tasksa_priority", "tasksa", ["priority"], unique=False)
    if not _column_exists("tasksa", "date_rollup_enabled"):
        op.add_column("tasksa", sa.Column("date_rollup_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _column_exists("tasksa", "source_action_item_id"):
        op.add_column("tasksa", sa.Column("source_action_item_id", sa.Integer(), nullable=True))
        op.create_index("ix_tasksa_source_action_item_id", "tasksa", ["source_action_item_id"], unique=False)
    if not _column_exists("tasksa", "blocked_by_task_id"):
        op.add_column("tasksa", sa.Column("blocked_by_task_id", sa.Integer(), nullable=True))
        op.create_index("ix_tasksa_blocked_by_task_id", "tasksa", ["blocked_by_task_id"], unique=False)

    if not _table_exists("taska_labels"):
        op.create_table(
            "taska_labels",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("color", sa.String(length=20), nullable=False, server_default="#6366f1"),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "name", name="uq_taska_label_project_name"),
        )
        op.create_index("ix_taska_labels_project_id", "taska_labels", ["project_id"], unique=False)

    if not _table_exists("taska_labels_assoc"):
        op.create_table(
            "taska_labels_assoc",
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("label_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["label_id"], ["taska_labels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("task_id", "label_id"),
        )

    if not _table_exists("taska_comments"):
        op.create_table(
            "taska_comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taska_comments_task_id", "taska_comments", ["task_id"], unique=False)
        op.create_index("ix_taska_comments_user_id", "taska_comments", ["user_id"], unique=False)
        op.create_index("ix_taska_comments_created_at", "taska_comments", ["created_at"], unique=False)

    if not _table_exists("taska_activities"):
        op.create_table(
            "taska_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taska_activities_task_id", "taska_activities", ["task_id"], unique=False)
        op.create_index("ix_taska_activities_user_id", "taska_activities", ["user_id"], unique=False)
        op.create_index("ix_taska_activities_created_at", "taska_activities", ["created_at"], unique=False)

    if not _column_exists("notifications", "task_id"):
        op.add_column("notifications", sa.Column("task_id", sa.Integer(), nullable=True))
        op.create_index("ix_notifications_task_id", "notifications", ["task_id"], unique=False)


def downgrade():
    if _column_exists("notifications", "task_id"):
        op.drop_index("ix_notifications_task_id", table_name="notifications")
        op.drop_constraint("fk_notifications_task_id", "notifications", type_="foreignkey")
        op.drop_column("notifications", "task_id")
    if _table_exists("taska_activities"):
        op.drop_table("taska_activities")
    if _table_exists("taska_comments"):
        op.drop_table("taska_comments")
    if _table_exists("taska_labels_assoc"):
        op.drop_table("taska_labels_assoc")
    if _table_exists("taska_labels"):
        op.drop_table("taska_labels")
    if _column_exists("tasksa", "blocked_by_task_id"):
        op.drop_index("ix_tasksa_blocked_by_task_id", table_name="tasksa")
        op.drop_constraint("fk_tasksa_blocked_by_task", "tasksa", type_="foreignkey")
        op.drop_column("tasksa", "blocked_by_task_id")
    if _column_exists("tasksa", "source_action_item_id"):
        op.drop_index("ix_tasksa_source_action_item_id", table_name="tasksa")
        op.drop_constraint("fk_tasksa_source_action_item", "tasksa", type_="foreignkey")
        op.drop_column("tasksa", "source_action_item_id")
    if _column_exists("tasksa", "date_rollup_enabled"):
        op.drop_column("tasksa", "date_rollup_enabled")
    if _column_exists("tasksa", "priority"):
        op.drop_index("ix_tasksa_priority", table_name="tasksa")
        op.drop_column("tasksa", "priority")
