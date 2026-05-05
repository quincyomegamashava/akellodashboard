"""add missing new creations topic columns

Revision ID: d9f14f3a7b21
Revises: c4d9e8a1f2b3
Create Date: 2026-04-30 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9f14f3a7b21"
down_revision = "c4d9e8a1f2b3"
branch_labels = None
depends_on = None


def _get_columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    table = "new_creations_topic_lessons"
    existing = _get_columns(table)

    if "created_by" not in existing:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f("ix_new_creations_topic_lessons_created_by"), ["created_by"], unique=False)
            batch_op.create_foreign_key(
                "fk_new_creations_topic_lessons_created_by_user",
                "user",
                ["created_by"],
                ["id"],
            )

    if "objectives" not in existing:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("objectives", sa.Text(), nullable=True))

    if "detailed_objectives" not in existing:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("detailed_objectives", sa.Text(), nullable=True))


def downgrade():
    table = "new_creations_topic_lessons"
    existing = _get_columns(table)

    with op.batch_alter_table(table, schema=None) as batch_op:
        if "created_by" in existing:
            batch_op.drop_constraint("fk_new_creations_topic_lessons_created_by_user", type_="foreignkey")
            batch_op.drop_index(batch_op.f("ix_new_creations_topic_lessons_created_by"))
            batch_op.drop_column("created_by")
        if "objectives" in existing:
            batch_op.drop_column("objectives")
        if "detailed_objectives" in existing:
            batch_op.drop_column("detailed_objectives")
