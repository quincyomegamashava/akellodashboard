"""Game races: mixed playlist multiplayer sessions."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists


revision = "i2j3k4l5m6n7"
down_revision = "h1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()

    if not table_exists(bind, "game_races"):
        op.create_table(
            "game_races",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("age_range", sa.String(length=20), nullable=False),
            sa.Column("starts_at", sa.DateTime(), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False),
            sa.Column("ends_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("is_cancelled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_game_races_starts_at", "game_races", ["starts_at"])
        op.create_index("ix_game_races_ends_at", "game_races", ["ends_at"])

    if not table_exists(bind, "game_race_items"):
        op.create_table(
            "game_race_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("race_id", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("item_type", sa.String(length=20), nullable=False),
            sa.Column("points", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["race_id"], ["game_races.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_game_race_items_race_id", "game_race_items", ["race_id"])

    if not table_exists(bind, "game_race_players"):
        op.create_table(
            "game_race_players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("race_id", sa.Integer(), nullable=False),
            sa.Column("game_user_id", sa.Integer(), nullable=False),
            sa.Column("joined_at", sa.DateTime(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("max_score", sa.Integer(), nullable=True),
            sa.Column("percentage", sa.Float(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("finished", sa.Boolean(), nullable=False),
            sa.Column("place", sa.Integer(), nullable=True),
            sa.Column("answers_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["race_id"], ["game_races.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["game_user_id"], ["game_users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("race_id", "game_user_id", name="uq_game_race_player"),
        )


def downgrade():
    bind = _bind()
    for table in ("game_race_players", "game_race_items", "game_races"):
        if table_exists(bind, table):
            op.drop_table(table)
