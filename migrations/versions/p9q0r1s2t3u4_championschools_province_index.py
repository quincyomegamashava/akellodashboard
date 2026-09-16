"""Add index on championschools.province for province stats queries."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists, index_exists


revision = "p9q0r1s2t3u4"
down_revision = "o8p9q0r1s2t3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not table_exists(bind, "championschools"):
        return
    if not index_exists(bind, "championschools", "ix_championschools_province"):
        op.create_index(
            "ix_championschools_province",
            "championschools",
            ["province"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if table_exists(bind, "championschools") and index_exists(
        bind, "championschools", "ix_championschools_province"
    ):
        op.drop_index("ix_championschools_province", table_name="championschools")
