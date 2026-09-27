"""Add galaxy_progress for solo Quiz Galaxy levels."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists


revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if table_exists(bind, "galaxy_progress"):
        return
    op.create_table(
        "galaxy_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_user_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("shell", sa.String(length=80), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("coaching_blurb", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_user_id"], ["game_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_user_id", "subject", "shell", name="uq_galaxy_progress_user_subject_shell"),
    )
    op.create_index("ix_galaxy_progress_game_user_id", "galaxy_progress", ["game_user_id"])
    op.create_index("ix_galaxy_progress_subject", "galaxy_progress", ["subject"])
    op.create_index("ix_galaxy_progress_shell", "galaxy_progress", ["shell"])


def downgrade():
    bind = op.get_bind()
    if table_exists(bind, "galaxy_progress"):
        op.drop_table("galaxy_progress")
