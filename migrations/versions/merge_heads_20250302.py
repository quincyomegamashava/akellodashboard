"""Merge multiple heads (champion/books branch and phone_number branch)

Revision ID: merge_heads_20250302
Revises: add_champion_school_requests, add_phone_number_game_users
Create Date: 2025-03-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_20250302'
down_revision = ('add_champion_school_requests', 'add_phone_number_game_users')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
