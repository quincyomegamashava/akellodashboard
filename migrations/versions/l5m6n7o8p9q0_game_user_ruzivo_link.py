"""Link game_users to Ruzivo/Smart Learning students."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import column_exists, create_index_if_missing, table_exists


revision = "l5m6n7o8p9q0"
down_revision = "k4l5m6n7o8p9"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, "game_users"):
        return

    if not column_exists(bind, "game_users", "ruzivo_student_id"):
        op.add_column("game_users", sa.Column("ruzivo_student_id", sa.Integer(), nullable=True))
    if not column_exists(bind, "game_users", "grade"):
        op.add_column("game_users", sa.Column("grade", sa.Integer(), nullable=True))
    if not column_exists(bind, "game_users", "auth_source"):
        op.add_column(
            "game_users",
            sa.Column("auth_source", sa.String(length=20), nullable=False, server_default="local"),
        )
    if not column_exists(bind, "game_users", "last_ruzivo_sync_at"):
        op.add_column("game_users", sa.Column("last_ruzivo_sync_at", sa.DateTime(), nullable=True))

    create_index_if_missing(bind, "ix_game_users_ruzivo_student_id", "game_users", ["ruzivo_student_id"], unique=True)


def downgrade():
    bind = _bind()
    if not table_exists(bind, "game_users"):
        return
    try:
        op.drop_index("ix_game_users_ruzivo_student_id", table_name="game_users")
    except Exception:
        pass
    for col in ("last_ruzivo_sync_at", "auth_source", "grade", "ruzivo_student_id"):
        if column_exists(bind, "game_users", col):
            op.drop_column("game_users", col)
