"""Student export history: stored original and processed workbooks."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists


revision = "j3k4l5m6n7o8"
down_revision = "i2j3k4l5m6n7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if table_exists(bind, "student_export_runs"):
        return

    op.create_table(
        "student_export_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("original_path", sa.String(length=512), nullable=False),
        sa.Column("processed_filename", sa.String(length=255), nullable=False),
        sa.Column("processed_path", sa.String(length=512), nullable=False),
        sa.Column("selected_sheets", sa.JSON(), nullable=True),
        sa.Column("column_mapping", sa.JSON(), nullable=True),
        sa.Column("summaries", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_export_runs_created_at",
        "student_export_runs",
        ["created_at"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    if not table_exists(bind, "student_export_runs"):
        return
    op.drop_index("ix_student_export_runs_created_at", table_name="student_export_runs")
    op.drop_table("student_export_runs")
