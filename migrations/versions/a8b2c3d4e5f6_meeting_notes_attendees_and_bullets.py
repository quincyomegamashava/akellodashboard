"""meeting notes attendees and focus_area text

Revision ID: a8b2c3d4e5f6
Revises: f71e8a9b0c1d
Create Date: 2026-05-19

"""
from alembic import op
import sqlalchemy as sa


revision = "a8b2c3d4e5f6"
down_revision = "f71e8a9b0c1d"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_names(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    if _table_exists("meeting_notes") and "guest_attendees" not in _column_names("meeting_notes"):
        op.add_column("meeting_notes", sa.Column("guest_attendees", sa.Text(), nullable=True))

    if not _table_exists("meeting_notes_attendees"):
        op.create_table(
            "meeting_notes_attendees",
            sa.Column("meeting_note_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["meeting_note_id"], ["meeting_notes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("meeting_note_id", "user_id"),
        )

    if _table_exists("meeting_notes_focus_rows"):
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        focus_cols = {c["name"]: c for c in inspector.get_columns("meeting_notes_focus_rows")}
        focus_area = focus_cols.get("focus_area")
        if focus_area and isinstance(focus_area.get("type"), sa.String):
            with op.batch_alter_table("meeting_notes_focus_rows", schema=None) as batch_op:
                batch_op.alter_column(
                    "focus_area",
                    existing_type=sa.String(length=255),
                    type_=sa.Text(),
                    existing_nullable=False,
                )


def downgrade():
    if _table_exists("meeting_notes_focus_rows"):
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        focus_cols = {c["name"]: c for c in inspector.get_columns("meeting_notes_focus_rows")}
        focus_area = focus_cols.get("focus_area")
        if focus_area and not isinstance(focus_area.get("type"), sa.String):
            with op.batch_alter_table("meeting_notes_focus_rows", schema=None) as batch_op:
                batch_op.alter_column(
                    "focus_area",
                    existing_type=sa.Text(),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                )
    if _table_exists("meeting_notes_attendees"):
        op.drop_table("meeting_notes_attendees")
    if _table_exists("meeting_notes") and "guest_attendees" in _column_names("meeting_notes"):
        op.drop_column("meeting_notes", "guest_attendees")
