"""Merge remaining heads (merge_heads + notifications/query_assignees)

Revision ID: merge_heads_final
Revises: merge_heads_20250302, 6184ab0cb50d
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_final'
down_revision = ('merge_heads_20250302', '6184ab0cb50d')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
