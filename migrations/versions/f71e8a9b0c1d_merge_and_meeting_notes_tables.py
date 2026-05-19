"""merge heads and add meeting notes tables

Revision ID: f71e8a9b0c1d
Revises: f0a1b2c3d4e5, f8a3b2c1d0e9
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa


revision = "f71e8a9b0c1d"
down_revision = ("f0a1b2c3d4e5", "f8a3b2c1d0e9")
branch_labels = None
depends_on = None


def _table_exists(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_names(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(table_name, index_name, columns, unique=False):
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    if not _table_exists("meeting_notes"):
        op.create_table(
            "meeting_notes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("meeting_date", sa.Date(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "meeting_notes", op.f("ix_meeting_notes_meeting_date"), ["meeting_date"]
    )
    _create_index_if_missing(
        "meeting_notes", op.f("ix_meeting_notes_created_by"), ["created_by"]
    )

    if not _table_exists("meeting_notes_focus_rows"):
        op.create_table(
            "meeting_notes_focus_rows",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_note_id", sa.Integer(), nullable=False),
            sa.Column("platform", sa.String(length=120), nullable=False),
            sa.Column("focus_area", sa.String(length=255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["meeting_note_id"], ["meeting_notes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "meeting_notes_focus_rows",
        op.f("ix_meeting_notes_focus_rows_meeting_note_id"),
        ["meeting_note_id"],
    )
    _create_index_if_missing(
        "meeting_notes_focus_rows",
        op.f("ix_meeting_notes_focus_rows_platform"),
        ["platform"],
    )

    if not _table_exists("meeting_notes_action_items"):
        op.create_table(
            "meeting_notes_action_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("focus_row_id", sa.Integer(), nullable=False),
            sa.Column("call_to_action", sa.Text(), nullable=False),
            sa.Column("expected_impact", sa.Text(), nullable=True),
            sa.Column("challenges", sa.Text(), nullable=True),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["focus_row_id"], ["meeting_notes_focus_rows.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "meeting_notes_action_items",
        op.f("ix_meeting_notes_action_items_focus_row_id"),
        ["focus_row_id"],
    )
    _create_index_if_missing(
        "meeting_notes_action_items",
        op.f("ix_meeting_notes_action_items_status"),
        ["status"],
    )
    _create_index_if_missing(
        "meeting_notes_action_items",
        op.f("ix_meeting_notes_action_items_due_date"),
        ["due_date"],
    )

    if not _table_exists("meeting_notes_action_assignees"):
        op.create_table(
            "meeting_notes_action_assignees",
            sa.Column("action_item_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["action_item_id"], ["meeting_notes_action_items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("action_item_id", "user_id"),
        )

    if not _table_exists("meeting_notes_activity_logs"):
        op.create_table(
            "meeting_notes_activity_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_note_id", sa.Integer(), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("summary", sa.String(length=512), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["meeting_note_id"], ["meeting_notes.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "meeting_notes_activity_logs",
        op.f("ix_meeting_notes_activity_logs_meeting_note_id"),
        ["meeting_note_id"],
    )
    _create_index_if_missing(
        "meeting_notes_activity_logs",
        op.f("ix_meeting_notes_activity_logs_actor_user_id"),
        ["actor_user_id"],
    )
    _create_index_if_missing(
        "meeting_notes_activity_logs",
        op.f("ix_meeting_notes_activity_logs_occurred_at"),
        ["occurred_at"],
    )
    _create_index_if_missing(
        "meeting_notes_activity_logs",
        op.f("ix_meeting_notes_activity_logs_entity_type"),
        ["entity_type"],
    )


def downgrade():
    if _table_exists("meeting_notes_activity_logs"):
        op.drop_index(op.f("ix_meeting_notes_activity_logs_entity_type"), table_name="meeting_notes_activity_logs")
        op.drop_index(op.f("ix_meeting_notes_activity_logs_occurred_at"), table_name="meeting_notes_activity_logs")
        op.drop_index(op.f("ix_meeting_notes_activity_logs_actor_user_id"), table_name="meeting_notes_activity_logs")
        op.drop_index(op.f("ix_meeting_notes_activity_logs_meeting_note_id"), table_name="meeting_notes_activity_logs")
        op.drop_table("meeting_notes_activity_logs")
    if _table_exists("meeting_notes_action_assignees"):
        op.drop_table("meeting_notes_action_assignees")
    if _table_exists("meeting_notes_action_items"):
        op.drop_index(op.f("ix_meeting_notes_action_items_due_date"), table_name="meeting_notes_action_items")
        op.drop_index(op.f("ix_meeting_notes_action_items_status"), table_name="meeting_notes_action_items")
        op.drop_index(op.f("ix_meeting_notes_action_items_focus_row_id"), table_name="meeting_notes_action_items")
        op.drop_table("meeting_notes_action_items")
    if _table_exists("meeting_notes_focus_rows"):
        op.drop_index(op.f("ix_meeting_notes_focus_rows_platform"), table_name="meeting_notes_focus_rows")
        op.drop_index(op.f("ix_meeting_notes_focus_rows_meeting_note_id"), table_name="meeting_notes_focus_rows")
        op.drop_table("meeting_notes_focus_rows")
    if _table_exists("meeting_notes"):
        op.drop_index(op.f("ix_meeting_notes_created_by"), table_name="meeting_notes")
        op.drop_index(op.f("ix_meeting_notes_meeting_date"), table_name="meeting_notes")
        op.drop_table("meeting_notes")
