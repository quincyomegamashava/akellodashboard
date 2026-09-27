"""Add galaxy_progress session fields for continue-later."""

from alembic import op

from app.migration_schema import add_column_if_missing, column_exists, table_exists


revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not table_exists(bind, "galaxy_progress"):
        return
    add_column_if_missing(
        bind,
        "galaxy_progress",
        "session_status",
        "session_status VARCHAR(20) NOT NULL DEFAULT 'idle'",
    )
    add_column_if_missing(
        bind,
        "galaxy_progress",
        "session_json",
        "session_json TEXT",
    )


def downgrade():
    bind = op.get_bind()
    if not table_exists(bind, "galaxy_progress"):
        return
    # Best-effort drop (SQLite may no-op via helper limitations)
    for col in ("session_json", "session_status"):
        if column_exists(bind, "galaxy_progress", col):
            try:
                op.drop_column("galaxy_progress", col)
            except Exception:
                pass
