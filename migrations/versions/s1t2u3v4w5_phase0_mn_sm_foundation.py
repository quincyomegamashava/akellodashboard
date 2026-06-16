"""Phase 0: stakeholder activities, saved views, notification lead FK."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import column_exists, fk_exists, index_exists, table_exists


revision = "s1t2u3v4w5"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def _table_exists(name):
    return table_exists(_bind(), name)


def _column_exists(table_name, column_name):
    return column_exists(_bind(), table_name, column_name)


def _index_exists(table_name, index_name):
    return index_exists(_bind(), table_name, index_name)


def _fk_exists(table_name, fk_name):
    return fk_exists(_bind(), table_name, fk_name)


def upgrade():
    if not _table_exists("sales_marketing_stakeholder_lead_activities"):
        op.create_table(
            "sales_marketing_stakeholder_lead_activities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("lead_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("activity_type", sa.String(length=64), nullable=False),
            sa.Column("summary", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("details_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["lead_id"],
                ["sales_marketing_stakeholder_leads.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sm_lead_activities_lead_id",
            "sales_marketing_stakeholder_lead_activities",
            ["lead_id"],
        )
        op.create_index(
            "ix_sm_lead_activities_created_at",
            "sales_marketing_stakeholder_lead_activities",
            ["created_at"],
        )

    if not _table_exists("sales_marketing_stakeholder_saved_views"):
        op.create_table(
            "sales_marketing_stakeholder_saved_views",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("filters_json", sa.JSON(), nullable=False),
            sa.Column("view_mode", sa.String(length=32), nullable=False, server_default="table"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sm_saved_views_user_id",
            "sales_marketing_stakeholder_saved_views",
            ["user_id"],
        )

    if _table_exists("notifications"):
        with op.batch_alter_table("notifications", schema=None) as batch_op:
            if not _column_exists("notifications", "stakeholder_lead_id"):
                batch_op.add_column(
                    sa.Column("stakeholder_lead_id", sa.Integer(), nullable=True)
                )
            if _column_exists("notifications", "stakeholder_lead_id") and not _fk_exists(
                "notifications", "fk_notifications_stakeholder_lead_id"
            ):
                batch_op.create_foreign_key(
                    "fk_notifications_stakeholder_lead_id",
                    "sales_marketing_stakeholder_leads",
                    ["stakeholder_lead_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if _column_exists("notifications", "stakeholder_lead_id") and not _index_exists(
                "notifications", "ix_notifications_stakeholder_lead_id"
            ):
                batch_op.create_index(
                    "ix_notifications_stakeholder_lead_id",
                    ["stakeholder_lead_id"],
                )

    # Backfill activities from existing notes
    if _table_exists("sales_marketing_stakeholder_lead_notes") and _table_exists(
        "sales_marketing_stakeholder_lead_activities"
    ):
        conn = op.get_bind()
        rows = conn.execute(
            sa.text(
                "SELECT id, lead_id, user_id, body, created_at "
                "FROM sales_marketing_stakeholder_lead_notes"
            )
        ).fetchall()
        for row in rows:
            conn.execute(
                sa.text(
                    "INSERT INTO sales_marketing_stakeholder_lead_activities "
                    "(lead_id, actor_user_id, activity_type, summary, details_json, created_at) "
                    "VALUES (:lead_id, :user_id, 'note_added', :summary, :details, :created_at)"
                ),
                {
                    "lead_id": row[1],
                    "user_id": row[2],
                    "summary": (row[3] or "")[:512],
                    "details": '{"note_id": %d}' % row[0],
                    "created_at": row[4],
                },
            )


def downgrade():
    if _table_exists("notifications"):
        with op.batch_alter_table("notifications", schema=None) as batch_op:
            batch_op.drop_index("ix_notifications_stakeholder_lead_id")
            batch_op.drop_constraint("fk_notifications_stakeholder_lead_id", type_="foreignkey")
            batch_op.drop_column("stakeholder_lead_id")
    op.drop_table("sales_marketing_stakeholder_saved_views")
    op.drop_table("sales_marketing_stakeholder_lead_activities")
