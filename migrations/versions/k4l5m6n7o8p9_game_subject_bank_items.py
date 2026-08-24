"""Add Game.subject and game_bank_items for HBC race bank selection."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists, column_exists


revision = "k4l5m6n7o8p9"
down_revision = "j3k4l5m6n7o8"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()

    if table_exists(bind, "games") and not column_exists(bind, "games", "subject"):
        op.add_column("games", sa.Column("subject", sa.String(length=120), nullable=True))
        op.create_index("ix_games_subject", "games", ["subject"])

    if not table_exists(bind, "game_bank_items"):
        op.create_table(
            "game_bank_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("subject", sa.String(length=120), nullable=True),
            sa.Column("age_range", sa.String(length=20), nullable=True),
            sa.Column("item_kind", sa.String(length=20), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("points_default", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_id", "slug", name="uq_game_bank_item_slug"),
        )
        op.create_index("ix_game_bank_items_game_id", "game_bank_items", ["game_id"])
        op.create_index("ix_game_bank_items_subject", "game_bank_items", ["subject"])
        op.create_index("ix_game_bank_items_age_range", "game_bank_items", ["age_range"])


def downgrade():
    bind = _bind()
    if table_exists(bind, "game_bank_items"):
        op.drop_table("game_bank_items")
    if table_exists(bind, "games") and column_exists(bind, "games", "subject"):
        op.drop_index("ix_games_subject", table_name="games")
        op.drop_column("games", "subject")
