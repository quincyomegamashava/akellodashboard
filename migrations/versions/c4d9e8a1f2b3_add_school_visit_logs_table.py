"""add school_visit_logs table

Revision ID: c4d9e8a1f2b3
Revises: b7c2e4a1d0f9
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d9e8a1f2b3'
down_revision = 'b7c2e4a1d0f9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'school_visit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('asl_school_id', sa.String(length=50), nullable=False),
        sa.Column('library_id', sa.String(length=50), nullable=False),
        sa.Column('school_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='checked_in'),
        sa.Column('checkin_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('checkout_at', sa.DateTime(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('checkin_latitude', sa.Float(), nullable=True),
        sa.Column('checkin_longitude', sa.Float(), nullable=True),
        sa.Column('location_text', sa.String(length=255), nullable=True),
        sa.Column('location_source', sa.String(length=20), nullable=False, server_default='unknown'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_school_visit_logs_user_id'), 'school_visit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_school_visit_logs_username'), 'school_visit_logs', ['username'], unique=False)
    op.create_index(op.f('ix_school_visit_logs_status'), 'school_visit_logs', ['status'], unique=False)
    op.create_index(op.f('ix_school_visit_logs_checkin_at'), 'school_visit_logs', ['checkin_at'], unique=False)
    op.create_index(op.f('ix_school_visit_logs_created_at'), 'school_visit_logs', ['created_at'], unique=False)
    op.create_index('ix_school_visit_logs_user_status', 'school_visit_logs', ['user_id', 'status'], unique=False)
    op.create_index('ix_school_visit_logs_user_checkin_desc', 'school_visit_logs', ['user_id', 'checkin_at'], unique=False)


def downgrade():
    op.drop_index('ix_school_visit_logs_user_checkin_desc', table_name='school_visit_logs')
    op.drop_index('ix_school_visit_logs_user_status', table_name='school_visit_logs')
    op.drop_index(op.f('ix_school_visit_logs_created_at'), table_name='school_visit_logs')
    op.drop_index(op.f('ix_school_visit_logs_checkin_at'), table_name='school_visit_logs')
    op.drop_index(op.f('ix_school_visit_logs_status'), table_name='school_visit_logs')
    op.drop_index(op.f('ix_school_visit_logs_username'), table_name='school_visit_logs')
    op.drop_index(op.f('ix_school_visit_logs_user_id'), table_name='school_visit_logs')
    op.drop_table('school_visit_logs')
