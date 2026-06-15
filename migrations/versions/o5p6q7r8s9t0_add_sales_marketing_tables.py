"""Add sales marketing tables."""

from alembic import op
import sqlalchemy as sa


revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None

DEFAULT_INTEREST = [
    "Need more information",
    "Request Akello training",
    "Request a demo",
    "Partnership enquiry",
    "Library / digital content interest",
    "Other",
]


def _table_exists(name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade():
    if not _table_exists("sales_marketing_events"):
        op.create_table(
            "sales_marketing_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sales_marketing_events_start_date", "sales_marketing_events", ["start_date"])
        op.create_index("ix_sales_marketing_events_end_date", "sales_marketing_events", ["end_date"])
        op.create_index("ix_sales_marketing_events_status", "sales_marketing_events", ["status"])

    if not _table_exists("sales_marketing_interest_options"):
        op.create_table(
            "sales_marketing_interest_options",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint("id"),
        )
        interest = sa.table(
            "sales_marketing_interest_options",
            sa.column("label", sa.String),
            sa.column("sort_order", sa.Integer),
            sa.column("is_active", sa.Boolean),
        )
        op.bulk_insert(
            interest,
            [{"label": lbl, "sort_order": i, "is_active": True} for i, lbl in enumerate(DEFAULT_INTEREST)],
        )

    if not _table_exists("sales_marketing_event_attendees"):
        op.create_table(
            "sales_marketing_event_attendees",
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["sales_marketing_events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("event_id", "user_id"),
        )

    if not _table_exists("sales_marketing_stakeholder_leads"):
        op.create_table(
            "sales_marketing_stakeholder_leads",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("occupation", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("mobile", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("school_name", sa.String(length=255), nullable=True),
            sa.Column("province", sa.String(length=120), nullable=True),
            sa.Column("organization", sa.String(length=255), nullable=True),
            sa.Column("role_category", sa.String(length=64), nullable=True),
            sa.Column("event_id", sa.Integer(), nullable=True),
            sa.Column("interest_option_id", sa.Integer(), nullable=True),
            sa.Column("preferred_contact", sa.String(length=32), nullable=True),
            sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("heard_about", sa.String(length=120), nullable=True),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="public_form"),
            sa.Column("is_duplicate_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["event_id"], ["sales_marketing_events.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["interest_option_id"], ["sales_marketing_interest_options.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sales_marketing_stakeholder_leads_email", "sales_marketing_stakeholder_leads", ["email"])
        op.create_index("ix_sales_marketing_stakeholder_leads_province", "sales_marketing_stakeholder_leads", ["province"])
        op.create_index("ix_sales_marketing_stakeholder_leads_event_id", "sales_marketing_stakeholder_leads", ["event_id"])
        op.create_index(
            "ix_sales_marketing_stakeholder_leads_interest_option_id",
            "sales_marketing_stakeholder_leads",
            ["interest_option_id"],
        )
        op.create_index(
            "ix_sales_marketing_stakeholder_leads_submitted_at",
            "sales_marketing_stakeholder_leads",
            ["submitted_at"],
        )

    if not _table_exists("sales_marketing_email_campaigns"):
        op.create_table(
            "sales_marketing_email_campaigns",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("subject", sa.String(length=500), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.Column("filter_snapshot", sa.JSON(), nullable=True),
            sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sales_marketing_email_campaigns_status", "sales_marketing_email_campaigns", ["status"])

    if not _table_exists("sales_marketing_email_campaign_recipients"):
        op.create_table(
            "sales_marketing_email_campaign_recipients",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("campaign_id", sa.Integer(), nullable=False),
            sa.Column("stakeholder_id", sa.Integer(), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.String(length=512), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["campaign_id"], ["sales_marketing_email_campaigns.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stakeholder_id"], ["sales_marketing_stakeholder_leads.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sales_marketing_email_campaign_recipients_campaign_id",
            "sales_marketing_email_campaign_recipients",
            ["campaign_id"],
        )

    if not _table_exists("sales_marketing_submission_rate_limits"):
        op.create_table(
            "sales_marketing_submission_rate_limits",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("ip_hash", sa.String(length=64), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_sales_marketing_submission_rate_limits_ip_hash",
            "sales_marketing_submission_rate_limits",
            ["ip_hash"],
        )


def downgrade():
    for tbl in [
        "sales_marketing_submission_rate_limits",
        "sales_marketing_email_campaign_recipients",
        "sales_marketing_email_campaigns",
        "sales_marketing_stakeholder_leads",
        "sales_marketing_event_attendees",
        "sales_marketing_interest_options",
        "sales_marketing_events",
    ]:
        if _table_exists(tbl):
            op.drop_table(tbl)
