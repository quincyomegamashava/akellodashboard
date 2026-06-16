"""Meeting notes planner upgrade: priority, labels, saved views, templates, comments."""

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


revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()

    if table_exists(bind, "meeting_notes_action_items"):
        add_column_if_missing(
            bind,
            "meeting_notes_action_items",
            "priority",
            "priority VARCHAR(16) NOT NULL DEFAULT 'medium'",
        )
        add_column_if_missing(bind, "meeting_notes_action_items", "source_excerpt", "source_excerpt TEXT")
        add_column_if_missing(
            bind,
            "meeting_notes_action_items",
            "ai_extracted",
            "ai_extracted BOOLEAN NOT NULL DEFAULT 0",
        )
        create_index_if_missing(
            bind,
            "ix_meeting_notes_action_items_priority",
            "meeting_notes_action_items",
            ["priority"],
        )

    if not table_exists(bind, "meeting_notes_labels"):
        op.create_table(
            "meeting_notes_labels",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("color", sa.String(length=7), nullable=False, server_default="#64748b"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    if not table_exists(bind, "meeting_notes_action_item_labels"):
        op.create_table(
            "meeting_notes_action_item_labels",
            sa.Column("action_item_id", sa.Integer(), nullable=False),
            sa.Column("label_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["action_item_id"], ["meeting_notes_action_items.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["label_id"], ["meeting_notes_labels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("action_item_id", "label_id"),
        )

    if not table_exists(bind, "meeting_notes_saved_views"):
        op.create_table(
            "meeting_notes_saved_views",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("filters_json", sa.JSON(), nullable=False),
            sa.Column("view_mode", sa.String(length=32), nullable=False, server_default="board"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_meeting_notes_saved_views_user_id",
            "meeting_notes_saved_views",
            ["user_id"],
            unique=False,
        )
    elif not index_exists(bind, "meeting_notes_saved_views", "ix_meeting_notes_saved_views_user_id"):
        op.create_index(
            "ix_meeting_notes_saved_views_user_id",
            "meeting_notes_saved_views",
            ["user_id"],
            unique=False,
        )

    if not table_exists(bind, "meeting_notes_templates"):
        op.create_table(
            "meeting_notes_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("title_pattern", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("summary_template", sa.Text(), nullable=True),
            sa.Column("focus_rows_json", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists(bind, "meeting_notes_item_comments"):
        op.create_table(
            "meeting_notes_item_comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("action_item_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["action_item_id"], ["meeting_notes_action_items.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["author_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_meeting_notes_item_comments_action_item_id",
            "meeting_notes_item_comments",
            ["action_item_id"],
            unique=False,
        )
        op.create_index(
            "ix_meeting_notes_item_comments_created_at",
            "meeting_notes_item_comments",
            ["created_at"],
            unique=False,
        )

    if table_exists(bind, "notifications"):
        add_column_if_missing(bind, "notifications", "meeting_note_id", "meeting_note_id INTEGER")
        add_column_if_missing(bind, "notifications", "action_item_id", "action_item_id INTEGER")
        with op.batch_alter_table("notifications", schema=None) as batch_op:
            if column_exists(bind, "notifications", "meeting_note_id") and not fk_exists(
                bind, "notifications", "fk_notifications_meeting_note_id"
            ):
                batch_op.create_foreign_key(
                    "fk_notifications_meeting_note_id",
                    "meeting_notes",
                    ["meeting_note_id"],
                    ["id"],
                )
            if column_exists(bind, "notifications", "action_item_id") and not fk_exists(
                bind, "notifications", "fk_notifications_action_item_id"
            ):
                batch_op.create_foreign_key(
                    "fk_notifications_action_item_id",
                    "meeting_notes_action_items",
                    ["action_item_id"],
                    ["id"],
                )
            if column_exists(bind, "notifications", "meeting_note_id") and not index_exists(
                bind, "notifications", "ix_notifications_meeting_note_id"
            ):
                batch_op.create_index("ix_notifications_meeting_note_id", ["meeting_note_id"], unique=False)
            if column_exists(bind, "notifications", "action_item_id") and not index_exists(
                bind, "notifications", "ix_notifications_action_item_id"
            ):
                batch_op.create_index("ix_notifications_action_item_id", ["action_item_id"], unique=False)


def downgrade():
    bind = _bind()
    if table_exists(bind, "notifications"):
        with op.batch_alter_table("notifications", schema=None) as batch_op:
            if index_exists(bind, "notifications", "ix_notifications_action_item_id"):
                batch_op.drop_index("ix_notifications_action_item_id")
            if index_exists(bind, "notifications", "ix_notifications_meeting_note_id"):
                batch_op.drop_index("ix_notifications_meeting_note_id")
            if fk_exists(bind, "notifications", "fk_notifications_action_item_id"):
                batch_op.drop_constraint("fk_notifications_action_item_id", type_="foreignkey")
            if fk_exists(bind, "notifications", "fk_notifications_meeting_note_id"):
                batch_op.drop_constraint("fk_notifications_meeting_note_id", type_="foreignkey")
            if column_exists(bind, "notifications", "action_item_id"):
                batch_op.drop_column("action_item_id")
            if column_exists(bind, "notifications", "meeting_note_id"):
                batch_op.drop_column("meeting_note_id")

    if table_exists(bind, "meeting_notes_item_comments"):
        op.drop_index("ix_meeting_notes_item_comments_created_at", table_name="meeting_notes_item_comments")
        op.drop_index("ix_meeting_notes_item_comments_action_item_id", table_name="meeting_notes_item_comments")
        op.drop_table("meeting_notes_item_comments")
    if table_exists(bind, "meeting_notes_templates"):
        op.drop_table("meeting_notes_templates")
    if table_exists(bind, "meeting_notes_saved_views"):
        op.drop_index("ix_meeting_notes_saved_views_user_id", table_name="meeting_notes_saved_views")
        op.drop_table("meeting_notes_saved_views")
    if table_exists(bind, "meeting_notes_action_item_labels"):
        op.drop_table("meeting_notes_action_item_labels")
    if table_exists(bind, "meeting_notes_labels"):
        op.drop_table("meeting_notes_labels")

    if table_exists(bind, "meeting_notes_action_items"):
        with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
            if index_exists(bind, "meeting_notes_action_items", "ix_meeting_notes_action_items_priority"):
                batch_op.drop_index("ix_meeting_notes_action_items_priority")
            if column_exists(bind, "meeting_notes_action_items", "ai_extracted"):
                batch_op.drop_column("ai_extracted")
            if column_exists(bind, "meeting_notes_action_items", "source_excerpt"):
                batch_op.drop_column("source_excerpt")
            if column_exists(bind, "meeting_notes_action_items", "priority"):
                batch_op.drop_column("priority")
