"""Add local DOB column on game_users for Ruzivo-synced learners."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import column_exists, table_exists


revision = "m6n7o8p9q0r1"
down_revision = "l5m6n7o8p9q0"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, "game_users"):
        return
    if not column_exists(bind, "game_users", "dob"):
        op.add_column("game_users", sa.Column("dob", sa.Date(), nullable=True))


def downgrade():
    bind = _bind()
    if table_exists(bind, "game_users") and column_exists(bind, "game_users", "dob"):
        op.drop_column("game_users", "dob")
