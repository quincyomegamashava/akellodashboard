from alembic import op

from app.migration_schema import add_column_if_missing


revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    add_column_if_missing(bind, "meeting_notes", "agenda_item_notes", "agenda_item_notes TEXT")
    add_column_if_missing(
        bind, "meeting_notes_focus_rows", "discussion_notes", "discussion_notes TEXT"
    )


def downgrade():
    bind = _bind()
    for table, col in (
        ("meeting_notes_focus_rows", "discussion_notes"),
        ("meeting_notes", "agenda_item_notes"),
    ):
        try:
            op.drop_column(table, col)
        except Exception:
            pass
