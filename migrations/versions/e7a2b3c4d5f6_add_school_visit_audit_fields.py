"""add school visit audit fields

Revision ID: e7a2b3c4d5f6
Revises: d9f14f3a7b21
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7a2b3c4d5f6'
down_revision = 'd9f14f3a7b21'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('school_visit_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checkout_latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('checkout_longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('checkout_location_text', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('checkout_location_source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('checkin_device_install_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('checkout_device_install_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('checkin_device_platform', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('checkin_user_agent', sa.String(length=512), nullable=True))
        batch_op.create_index(batch_op.f('ix_school_visit_logs_checkin_device_install_id'), ['checkin_device_install_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_school_visit_logs_checkout_device_install_id'), ['checkout_device_install_id'], unique=False)


def downgrade():
    with op.batch_alter_table('school_visit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_school_visit_logs_checkout_device_install_id'))
        batch_op.drop_index(batch_op.f('ix_school_visit_logs_checkin_device_install_id'))
        batch_op.drop_column('checkin_user_agent')
        batch_op.drop_column('checkin_device_platform')
        batch_op.drop_column('checkout_device_install_id')
        batch_op.drop_column('checkin_device_install_id')
        batch_op.drop_column('checkout_location_source')
        batch_op.drop_column('checkout_location_text')
        batch_op.drop_column('checkout_longitude')
        batch_op.drop_column('checkout_latitude')
