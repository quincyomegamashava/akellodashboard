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


def _column_exists(connection, table, column):
    """Return True if column exists in table (SQLite)."""
    result = connection.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade():
    conn = op.get_bind()

    # Add age column to game_users table (skip if already exists from partial run)
    if not _column_exists(conn, 'game_users', 'age'):
        op.add_column('game_users', sa.Column('age', sa.Integer(), nullable=True))
    # Update existing records with a default age (you may want to set this manually)
    op.execute("UPDATE game_users SET age = 12 WHERE age IS NULL")
    # Make age non-nullable: use batch_alter_table for SQLite (no direct ALTER COLUMN)
    with op.batch_alter_table('game_users', schema=None) as batch_op:
        batch_op.alter_column('age', existing_type=sa.Integer(), nullable=False)

    # Add age_range column to games table (skip if already exists)
    if not _column_exists(conn, 'games', 'age_range'):
        op.add_column('games', sa.Column('age_range', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('games', 'age_range')
    op.drop_column('game_users', 'age')


