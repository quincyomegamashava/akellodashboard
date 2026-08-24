"""Help Desk support hub: unified ticket fields + related tables."""

from alembic import op
import sqlalchemy as sa

from app.migration_schema import (
    add_column_if_missing,
    create_index_if_missing,
    table_exists,
)


revision = "h1d2e3f4a5b6"
down_revision = ("b1c2d3e4f5a6", "z3a4b5c6d7e8")
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()

    if not table_exists(bind, "helpdesk_teams"):
        op.create_table(
            "helpdesk_teams",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    if not table_exists(bind, "helpdesk_team_members"):
        op.create_table(
            "helpdesk_team_members",
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["helpdesk_teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("team_id", "user_id"),
        )

    if table_exists(bind, "helpdesk_queries"):
        add_column_if_missing(bind, "helpdesk_queries", "source", "source VARCHAR(20) DEFAULT 'internal' NOT NULL")
        add_column_if_missing(bind, "helpdesk_queries", "priority", "priority VARCHAR(20) DEFAULT 'normal' NOT NULL")
        add_column_if_missing(bind, "helpdesk_queries", "category", "category VARCHAR(40) DEFAULT 'general' NOT NULL")
        add_column_if_missing(bind, "helpdesk_queries", "requester_email", "requester_email VARCHAR(255)")
        add_column_if_missing(bind, "helpdesk_queries", "first_response_at", "first_response_at DATETIME")
        add_column_if_missing(bind, "helpdesk_queries", "sla_first_response_due", "sla_first_response_due DATETIME")
        add_column_if_missing(bind, "helpdesk_queries", "sla_resolve_due", "sla_resolve_due DATETIME")
        add_column_if_missing(bind, "helpdesk_queries", "sla_breached", "sla_breached BOOLEAN DEFAULT 0 NOT NULL")
        add_column_if_missing(bind, "helpdesk_queries", "team_id", "team_id INTEGER")
        add_column_if_missing(bind, "helpdesk_queries", "message_id", "message_id VARCHAR(500)")
        create_index_if_missing(bind, "ix_helpdesk_queries_source", "helpdesk_queries", ["source"])
        create_index_if_missing(bind, "ix_helpdesk_queries_priority", "helpdesk_queries", ["priority"])
        create_index_if_missing(bind, "ix_helpdesk_queries_category", "helpdesk_queries", ["category"])
        create_index_if_missing(bind, "ix_helpdesk_queries_requester_email", "helpdesk_queries", ["requester_email"])
        create_index_if_missing(bind, "ix_helpdesk_queries_sla_first_response_due", "helpdesk_queries", ["sla_first_response_due"])
        create_index_if_missing(bind, "ix_helpdesk_queries_sla_resolve_due", "helpdesk_queries", ["sla_resolve_due"])
        create_index_if_missing(bind, "ix_helpdesk_queries_sla_breached", "helpdesk_queries", ["sla_breached"])
        create_index_if_missing(bind, "ix_helpdesk_queries_team_id", "helpdesk_queries", ["team_id"])
        create_index_if_missing(bind, "ix_helpdesk_queries_message_id", "helpdesk_queries", ["message_id"], unique=True)

    if not table_exists(bind, "helpdesk_watchers"):
        op.create_table(
            "helpdesk_watchers",
            sa.Column("query_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["query_id"], ["helpdesk_queries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("query_id", "user_id"),
        )

    if not table_exists(bind, "helpdesk_messages"):
        op.create_table(
            "helpdesk_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("query_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column("author_name", sa.String(length=120), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["author_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["query_id"], ["helpdesk_queries.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing(bind, "ix_helpdesk_messages_query_id", "helpdesk_messages", ["query_id"])
    create_index_if_missing(bind, "ix_helpdesk_messages_author_id", "helpdesk_messages", ["author_id"])
    create_index_if_missing(bind, "ix_helpdesk_messages_is_internal", "helpdesk_messages", ["is_internal"])
    create_index_if_missing(bind, "ix_helpdesk_messages_created_at", "helpdesk_messages", ["created_at"])

    if not table_exists(bind, "helpdesk_attachments"):
        op.create_table(
            "helpdesk_attachments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("query_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=True),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["message_id"], ["helpdesk_messages.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["query_id"], ["helpdesk_queries.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing(bind, "ix_helpdesk_attachments_query_id", "helpdesk_attachments", ["query_id"])
    create_index_if_missing(bind, "ix_helpdesk_attachments_message_id", "helpdesk_attachments", ["message_id"])

    if not table_exists(bind, "helpdesk_macros"):
        op.create_table(
            "helpdesk_macros",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index_if_missing(bind, "ix_helpdesk_macros_category", "helpdesk_macros", ["category"])

    if not table_exists(bind, "helpdesk_articles"):
        op.create_table(
            "helpdesk_articles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("tags", sa.String(length=255), nullable=True),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
    create_index_if_missing(bind, "ix_helpdesk_articles_slug", "helpdesk_articles", ["slug"], unique=True)
    create_index_if_missing(bind, "ix_helpdesk_articles_published", "helpdesk_articles", ["published"])

    if not table_exists(bind, "helpdesk_csat"):
        op.create_table(
            "helpdesk_csat",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("query_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["query_id"], ["helpdesk_queries.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("query_id"),
        )
    create_index_if_missing(bind, "ix_helpdesk_csat_query_id", "helpdesk_csat", ["query_id"], unique=True)


def downgrade():
    bind = _bind()
    for table in (
        "helpdesk_csat",
        "helpdesk_articles",
        "helpdesk_macros",
        "helpdesk_attachments",
        "helpdesk_messages",
        "helpdesk_watchers",
        "helpdesk_team_members",
        "helpdesk_teams",
    ):
        if table_exists(bind, table):
            op.drop_table(table)
