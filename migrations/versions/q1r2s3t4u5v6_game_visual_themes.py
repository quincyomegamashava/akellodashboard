"""Add race visual themes and solo survival theme settings."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import add_column_if_missing, column_exists


revision = "q1r2s3t4u5v6"
down_revision = "p9q0r1s2t3u4"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    add_column_if_missing(
        bind,
        "game_races",
        "visual_theme",
        "visual_theme VARCHAR(30) NOT NULL DEFAULT 'car'",
    )
    add_column_if_missing(
        bind,
        "games",
        "solo_theme",
        "solo_theme VARCHAR(30) NOT NULL DEFAULT 'swim'",
    )
    add_column_if_missing(
        bind,
        "games",
        "solo_time_limit_seconds",
        "solo_time_limit_seconds INTEGER",
    )


def downgrade():
    bind = _bind()
    for table, column in (
        ("games", "solo_time_limit_seconds"),
        ("games", "solo_theme"),
        ("game_races", "visual_theme"),
    ):
        if column_exists(bind, table, column):
            try:
                bind.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN "{column}"'))
            except Exception:
                pass
