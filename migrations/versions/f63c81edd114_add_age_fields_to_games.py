"""Add age fields to games and game users

Revision ID: f63c81edd114
Revises: 0b6082487ca7
Create Date: 2025-01-28 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f63c81edd114'
down_revision = '0b6082487ca7'
branch_labels = None
depends_on = None


def upgrade():
    # Add age column to game_users table
    op.add_column('game_users', sa.Column('age', sa.Integer(), nullable=True))
    # Update existing records with a default age (you may want to set this manually)
    op.execute("UPDATE game_users SET age = 12 WHERE age IS NULL")
    # Make age non-nullable after setting defaults
    op.alter_column('game_users', 'age', nullable=False)
    
    # Add age_range column to games table
    op.add_column('games', sa.Column('age_range', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('games', 'age_range')
    op.drop_column('game_users', 'age')


