"""Add tickets table for email helpdesk

Revision ID: add_tickets_email
Revises: merge_heads_final
Create Date: 2026-03-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_tickets_email'
down_revision = 'merge_heads_final'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('message_id', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tickets_message_id'), 'tickets', ['message_id'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_tickets_message_id'), table_name='tickets')
    op.drop_table('tickets')
