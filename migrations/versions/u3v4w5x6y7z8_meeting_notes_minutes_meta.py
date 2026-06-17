from alembic import op
import sqlalchemy as sa

from app.migration_schema import add_column_if_missing


revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    add_column_if_missing(bind, "meeting_notes", "location", "location VARCHAR(255)")
    add_column_if_missing(bind, "meeting_notes", "meeting_time", "meeting_time VARCHAR(32)")
    add_column_if_missing(bind, "meeting_notes", "agenda", "agenda TEXT")


def downgrade():
    bind = _bind()
    for col in ("agenda", "meeting_time", "location"):
        try:
            op.drop_column("meeting_notes", col)
        except Exception:
            pass
