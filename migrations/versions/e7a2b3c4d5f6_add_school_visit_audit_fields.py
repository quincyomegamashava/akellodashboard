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


def _get_columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col['name'] for col in inspector.get_columns(table_name)}


def _index_names(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index['name'] for index in inspector.get_indexes(table_name)}


def upgrade():
    existing = _get_columns('school_visit_logs')
    existing_indexes = _index_names('school_visit_logs')

    with op.batch_alter_table('school_visit_logs', schema=None) as batch_op:
        if 'checkout_latitude' not in existing:
            batch_op.add_column(sa.Column('checkout_latitude', sa.Float(), nullable=True))
        if 'checkout_longitude' not in existing:
            batch_op.add_column(sa.Column('checkout_longitude', sa.Float(), nullable=True))
        if 'checkout_location_text' not in existing:
            batch_op.add_column(sa.Column('checkout_location_text', sa.String(length=255), nullable=True))
        if 'checkout_location_source' not in existing:
            batch_op.add_column(sa.Column('checkout_location_source', sa.String(length=20), nullable=True))
        if 'checkin_device_install_id' not in existing:
            batch_op.add_column(sa.Column('checkin_device_install_id', sa.String(length=64), nullable=True))
        if 'checkout_device_install_id' not in existing:
            batch_op.add_column(sa.Column('checkout_device_install_id', sa.String(length=64), nullable=True))
        if 'checkin_device_platform' not in existing:
            batch_op.add_column(sa.Column('checkin_device_platform', sa.String(length=32), nullable=True))
        if 'checkin_user_agent' not in existing:
            batch_op.add_column(sa.Column('checkin_user_agent', sa.String(length=512), nullable=True))
        if 'ix_school_visit_logs_checkin_device_install_id' not in existing_indexes:
            batch_op.create_index(batch_op.f('ix_school_visit_logs_checkin_device_install_id'), ['checkin_device_install_id'], unique=False)
        if 'ix_school_visit_logs_checkout_device_install_id' not in existing_indexes:
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
