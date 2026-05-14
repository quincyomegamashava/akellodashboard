"""add school visit context fields (grades, teacher)

Revision ID: f0a1b2c3d4e5
Revises: e7a2b3c4d5f6
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa


revision = 'f0a1b2c3d4e5'
down_revision = 'e7a2b3c4d5f6'
branch_labels = None
depends_on = None


def _get_columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col['name'] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _get_columns('school_visit_logs')
    with op.batch_alter_table('school_visit_logs', schema=None) as batch_op:
        if 'visit_grades_json' not in existing:
            batch_op.add_column(sa.Column('visit_grades_json', sa.Text(), nullable=True))
        if 'teacher_name' not in existing:
            batch_op.add_column(sa.Column('teacher_name', sa.String(length=255), nullable=True))
        if 'teacher_contact' not in existing:
            batch_op.add_column(sa.Column('teacher_contact', sa.String(length=255), nullable=True))


def downgrade():
    existing = _get_columns('school_visit_logs')
    with op.batch_alter_table('school_visit_logs', schema=None) as batch_op:
        if 'teacher_contact' in existing:
            batch_op.drop_column('teacher_contact')
        if 'teacher_name' in existing:
            batch_op.drop_column('teacher_name')
        if 'visit_grades_json' in existing:
            batch_op.drop_column('visit_grades_json')
