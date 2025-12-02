"""Add difficulty_level to games

Revision ID: 0362a438d8c
Revises: efbe1a7d2066
Create Date: 2025-01-28 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0362a438d8c'
down_revision = 'efbe1a7d2066'
branch_labels = None
depends_on = None


def upgrade():
    # Add difficulty_level column to games table
    op.add_column('games', sa.Column('difficulty_level', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('games', 'difficulty_level')

