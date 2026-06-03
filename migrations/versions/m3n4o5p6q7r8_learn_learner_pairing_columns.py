"""Add learner pairing columns for guardian linking."""

from alembic import op
import sqlalchemy as sa


revision = "m3n4o5p6q7r8"
down_revision = "h9i8j7k6l5m4"
branch_labels = None
depends_on = None


def _cols(table):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    cols = _cols("learn_learners")
    if "pairing_code" not in cols:
        op.add_column("learn_learners", sa.Column("pairing_code", sa.String(16), nullable=True))
        op.create_index("ix_learn_learners_pairing_code", "learn_learners", ["pairing_code"])
    if "pairing_expires_at" not in cols:
        op.add_column("learn_learners", sa.Column("pairing_expires_at", sa.DateTime(), nullable=True))


def downgrade():
    cols = _cols("learn_learners")
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = {ix["name"] for ix in insp.get_indexes("learn_learners")}
    if "ix_learn_learners_pairing_code" in indexes:
        op.drop_index("ix_learn_learners_pairing_code", table_name="learn_learners")
    if "pairing_expires_at" in cols:
        op.drop_column("learn_learners", "pairing_expires_at")
    if "pairing_code" in cols:
        op.drop_column("learn_learners", "pairing_code")
