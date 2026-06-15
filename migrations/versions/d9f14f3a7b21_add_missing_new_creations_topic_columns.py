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


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name):
    return table_name in _inspector().get_table_names()


def _get_columns(table_name):
    return {col["name"] for col in _inspector().get_columns(table_name)}


def _ensure_new_creations_tables():
    if _table_exists("new_creations_curriculums"):
        return

    op.create_table(
        "new_creations_curriculums",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("new_creations_curriculums", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_new_creations_curriculums_created_by"), ["created_by"], unique=False)
        batch_op.create_index(batch_op.f("ix_new_creations_curriculums_name"), ["name"], unique=True)

    op.create_table(
        "new_creations_grades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("curriculum_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["curriculum_id"], ["new_creations_curriculums.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("new_creations_grades", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_new_creations_grades_curriculum_id"), ["curriculum_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_new_creations_grades_name"), ["name"], unique=False)

    op.create_table(
        "new_creations_subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("grade_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["grade_id"], ["new_creations_grades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("new_creations_subjects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_new_creations_subjects_grade_id"), ["grade_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_new_creations_subjects_name"), ["name"], unique=False)

    op.create_table(
        "new_creations_topic_lessons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("questions", sa.Text(), nullable=True),
        sa.Column("objectives", sa.Text(), nullable=True),
        sa.Column("detailed_objectives", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["new_creations_subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("new_creations_topic_lessons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_new_creations_topic_lessons_created_by"), ["created_by"], unique=False)
        batch_op.create_index(batch_op.f("ix_new_creations_topic_lessons_subject_id"), ["subject_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_new_creations_topic_lessons_title"), ["title"], unique=False)


def upgrade():
    _ensure_new_creations_tables()

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
