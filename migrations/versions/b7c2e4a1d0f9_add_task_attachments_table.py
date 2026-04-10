"""add task_attachments table

Revision ID: b7c2e4a1d0f9
Revises: a4f490e90d0e
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa


revision = "b7c2e4a1d0f9"
down_revision = "a4f490e90d0e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasksa.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("task_attachments")
