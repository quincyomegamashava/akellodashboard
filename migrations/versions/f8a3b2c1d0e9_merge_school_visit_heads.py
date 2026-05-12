"""merge school visit migration heads

Revision ID: f8a3b2c1d0e9
Revises: e7a2b3c4d5f6, 900c2e62da0e
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8a3b2c1d0e9'
down_revision = ('e7a2b3c4d5f6', '900c2e62da0e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
