"""PM platform roadmap: custom fields, milestones, programs, roles, etc."""

from alembic import op
import sqlalchemy as sa


revision = "a9b8c7d6e5f4"
down_revision = "z3a4b5c6d7e8"
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
    if not _column_exists("project_membersa", "role"):
        op.add_column(
            "project_membersa",
            sa.Column("role", sa.String(length=20), nullable=False, server_default="contributor"),
        )

    if not _column_exists("columnsa", "workflow_rules"):
        op.add_column("columnsa", sa.Column("workflow_rules", sa.Text(), nullable=True))

    if not _table_exists("projecta_custom_fields"):
        op.create_table(
            "projecta_custom_fields",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("field_type", sa.String(length=20), nullable=False, server_default="text"),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("required_on_close", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projecta_custom_fields_project_id", "projecta_custom_fields", ["project_id"])

    if not _table_exists("taska_custom_field_values"):
        op.create_table(
            "taska_custom_field_values",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("field_id", sa.Integer(), nullable=False),
            sa.Column("value_text", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["field_id"], ["projecta_custom_fields.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", "field_id", name="uq_taska_custom_field_value"),
        )
        op.create_index("ix_taska_custom_field_values_task_id", "taska_custom_field_values", ["task_id"])
        op.create_index("ix_taska_custom_field_values_field_id", "taska_custom_field_values", ["field_id"])

    if not _table_exists("projecta_saved_views"):
        op.create_table(
            "projecta_saved_views",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("filter_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projecta_saved_views_project_id", "projecta_saved_views", ["project_id"])
        op.create_index("ix_projecta_saved_views_user_id", "projecta_saved_views", ["user_id"])

    if not _table_exists("taska_dependencies"):
        op.create_table(
            "taska_dependencies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("depends_on_task_id", sa.Integer(), nullable=False),
            sa.Column("dep_type", sa.String(length=20), nullable=False, server_default="finish_to_start"),
            sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_taska_dependency"),
        )
        op.create_index("ix_taska_dependencies_task_id", "taska_dependencies", ["task_id"])
        op.create_index("ix_taska_dependencies_depends_on", "taska_dependencies", ["depends_on_task_id"])

    if not _table_exists("milestonesa"):
        op.create_table(
            "milestonesa",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("due_date", sa.DateTime(), nullable=True),
            sa.Column("color", sa.String(length=20), nullable=False, server_default="#8b5cf6"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_milestonesa_project_id", "milestonesa", ["project_id"])

    if not _table_exists("milestone_tasks_assoc"):
        op.create_table(
            "milestone_tasks_assoc",
            sa.Column("milestone_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["milestone_id"], ["milestonesa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("milestone_id", "task_id"),
        )

    if not _table_exists("projecta_baselines"):
        op.create_table(
            "projecta_baselines",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projecta_baselines_project_id", "projecta_baselines", ["project_id"])

    if not _table_exists("programsa"):
        op.create_table(
            "programsa",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=140), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("program_projects_assoc"):
        op.create_table(
            "program_projects_assoc",
            sa.Column("program_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["program_id"], ["programsa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("program_id", "project_id"),
        )

    if not _table_exists("projecta_stats_snapshots"):
        op.create_table(
            "projecta_stats_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("total_tasks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_tasks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overdue_tasks", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projecta_stats_snapshots_project_id", "projecta_stats_snapshots", ["project_id"])
        op.create_index("ix_projecta_stats_snapshots_date", "projecta_stats_snapshots", ["snapshot_date"])

    if not _table_exists("taska_time_entries"):
        op.create_table(
            "taska_time_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taska_time_entries_task_id", "taska_time_entries", ["task_id"])
        op.create_index("ix_taska_time_entries_user_id", "taska_time_entries", ["user_id"])

    if not _table_exists("projecta_webhooks"):
        op.create_table(
            "projecta_webhooks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("url", sa.String(length=512), nullable=False),
            sa.Column("events_json", sa.Text(), nullable=False),
            sa.Column("secret", sa.String(length=64), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_projecta_webhooks_project_id", "projecta_webhooks", ["project_id"])

    if not _table_exists("projecta_subscriptions"):
        op.create_table(
            "projecta_subscriptions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projectsa.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "user_id", name="uq_projecta_subscription"),
        )
        op.create_index("ix_projecta_subscriptions_project_id", "projecta_subscriptions", ["project_id"])
        op.create_index("ix_projecta_subscriptions_user_id", "projecta_subscriptions", ["user_id"])

    if not _table_exists("taska_comment_mentions"):
        op.create_table(
            "taska_comment_mentions",
            sa.Column("comment_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["comment_id"], ["taska_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("comment_id", "user_id"),
        )


def downgrade():
    for tbl in (
        "taska_comment_mentions",
        "projecta_subscriptions",
        "projecta_webhooks",
        "taska_time_entries",
        "projecta_stats_snapshots",
        "program_projects_assoc",
        "programsa",
        "projecta_baselines",
        "milestone_tasks_assoc",
        "milestonesa",
        "taska_dependencies",
        "projecta_saved_views",
        "taska_custom_field_values",
        "projecta_custom_fields",
    ):
        if _table_exists(tbl):
            op.drop_table(tbl)
    if _column_exists("columnsa", "workflow_rules"):
        op.drop_column("columnsa", "workflow_rules")
    if _column_exists("project_membersa", "role"):
        op.drop_column("project_membersa", "role")
