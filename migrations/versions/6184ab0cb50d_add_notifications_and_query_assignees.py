"""Add notifications and query assignees

Revision ID: 6184ab0cb50d
Revises: f63c81edd114
Create Date: 2026-01-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6184ab0cb50d'
down_revision = 'f63c81edd114'
branch_labels = None
depends_on = None


def upgrade():
    # Create query_assignees junction table
    op.create_table('query_assignees',
        sa.Column('query_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['query_id'], ['helpdesk_queries.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('query_id', 'user_id')
    )
    
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query_id', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('read', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['query_id'], ['helpdesk_queries.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_read'), 'notifications', ['read'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    
    # Add resolved_at column to helpdesk_queries
    op.add_column('helpdesk_queries', sa.Column('resolved_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove resolved_at column
    op.drop_column('helpdesk_queries', 'resolved_at')
    
    # Drop notifications table
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    
    # Drop query_assignees table
    op.drop_table('query_assignees')

