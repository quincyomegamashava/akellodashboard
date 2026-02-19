"""Add champion_school_requests table

Revision ID: add_champion_school_requests
Revises: 0362a438d8c
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_champion_school_requests'
down_revision = '0362a438d8c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('champion_school_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('champion_school_id', sa.Integer(), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('asl_school_id', sa.String(length=50), nullable=True),
        sa.Column('library_school_id', sa.String(length=50), nullable=True),
        sa.Column('school_name', sa.String(length=255), nullable=False),
        sa.Column('province', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Pending'),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['champion_school_id'], ['championschools.id'], ),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_champion_school_requests_champion_school_id'), 'champion_school_requests', ['champion_school_id'], unique=False)
    op.create_index(op.f('ix_champion_school_requests_requested_by_user_id'), 'champion_school_requests', ['requested_by_user_id'], unique=False)
    op.create_index(op.f('ix_champion_school_requests_status'), 'champion_school_requests', ['status'], unique=False)
    op.create_index(op.f('ix_champion_school_requests_created_at'), 'champion_school_requests', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_champion_school_requests_created_at'), table_name='champion_school_requests')
    op.drop_index(op.f('ix_champion_school_requests_status'), table_name='champion_school_requests')
    op.drop_index(op.f('ix_champion_school_requests_requested_by_user_id'), table_name='champion_school_requests')
    op.drop_index(op.f('ix_champion_school_requests_champion_school_id'), table_name='champion_school_requests')
    op.drop_table('champion_school_requests')
