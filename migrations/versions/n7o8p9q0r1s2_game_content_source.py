"""Add content_source and Ruzivo link fields on games."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import column_exists, table_exists


revision = "n7o8p9q0r1s2"
down_revision = "m6n7o8p9q0r1"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, "games"):
        return
    if not column_exists(bind, "games", "content_source"):
        op.add_column(
            "games",
            sa.Column("content_source", sa.String(length=30), nullable=False, server_default="general_knowledge"),
        )
        op.create_index("ix_games_content_source", "games", ["content_source"], unique=False)
    if not column_exists(bind, "games", "ruzivo_ex_id"):
        op.add_column("games", sa.Column("ruzivo_ex_id", sa.Integer(), nullable=True))
        op.create_index("ix_games_ruzivo_ex_id", "games", ["ruzivo_ex_id"], unique=False)
    if not column_exists(bind, "games", "ruzivo_source"):
        op.add_column("games", sa.Column("ruzivo_source", sa.String(length=20), nullable=True))
    if not column_exists(bind, "games", "grade"):
        op.add_column("games", sa.Column("grade", sa.Integer(), nullable=True))
        op.create_index("ix_games_grade", "games", ["grade"], unique=False)


def downgrade():
    bind = _bind()
    if not table_exists(bind, "games"):
        return
    for col, idx in (
        ("grade", "ix_games_grade"),
        ("ruzivo_source", None),
        ("ruzivo_ex_id", "ix_games_ruzivo_ex_id"),
        ("content_source", "ix_games_content_source"),
    ):
        if column_exists(bind, "games", col):
            if idx:
                try:
                    op.drop_index(idx, table_name="games")
                except Exception:
                    pass
            op.drop_column("games", col)
