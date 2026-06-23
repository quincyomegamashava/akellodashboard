"""PM webhook delivery log table."""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if _table_exists("projecta_webhook_deliveries"):
        return
    op.create_table(
        "projecta_webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("webhook_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["webhook_id"], ["projecta_webhooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_projecta_webhook_deliveries_webhook_id",
        "projecta_webhook_deliveries",
        ["webhook_id"],
    )
    op.create_index(
        "ix_projecta_webhook_deliveries_created_at",
        "projecta_webhook_deliveries",
        ["created_at"],
    )


def downgrade():
    if not _table_exists("projecta_webhook_deliveries"):
        return
    op.drop_index("ix_projecta_webhook_deliveries_created_at", table_name="projecta_webhook_deliveries")
    op.drop_index("ix_projecta_webhook_deliveries_webhook_id", table_name="projecta_webhook_deliveries")
    op.drop_table("projecta_webhook_deliveries")
