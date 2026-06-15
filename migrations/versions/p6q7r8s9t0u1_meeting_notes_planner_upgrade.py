"""Meeting notes planner upgrade: priority, labels, saved views, templates, comments."""

from alembic import op
import sqlalchemy as sa


revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium")
        )
        batch_op.add_column(sa.Column("source_excerpt", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("ai_extracted", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_index("ix_meeting_notes_action_items_priority", ["priority"], unique=False)

    op.create_table(
        "meeting_notes_labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False, server_default="#64748b"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "meeting_notes_action_item_labels",
        sa.Column("action_item_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_item_id"], ["meeting_notes_action_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["label_id"], ["meeting_notes_labels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("action_item_id", "label_id"),
    )

    op.create_table(
        "meeting_notes_saved_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("view_mode", sa.String(length=32), nullable=False, server_default="board"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_notes_saved_views_user_id",
        "meeting_notes_saved_views",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "meeting_notes_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("title_pattern", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("summary_template", sa.Text(), nullable=True),
        sa.Column("focus_rows_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "meeting_notes_item_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_item_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_item_id"], ["meeting_notes_action_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_notes_item_comments_action_item_id",
        "meeting_notes_item_comments",
        ["action_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_meeting_notes_item_comments_created_at",
        "meeting_notes_item_comments",
        ["created_at"],
        unique=False,
    )

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("meeting_note_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("action_item_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notifications_meeting_note_id",
            "meeting_notes",
            ["meeting_note_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_notifications_action_item_id",
            "meeting_notes_action_items",
            ["action_item_id"],
            ["id"],
        )
        batch_op.create_index("ix_notifications_meeting_note_id", ["meeting_note_id"], unique=False)
        batch_op.create_index("ix_notifications_action_item_id", ["action_item_id"], unique=False)


def downgrade():
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_action_item_id")
        batch_op.drop_index("ix_notifications_meeting_note_id")
        batch_op.drop_constraint("fk_notifications_action_item_id", type_="foreignkey")
        batch_op.drop_constraint("fk_notifications_meeting_note_id", type_="foreignkey")
        batch_op.drop_column("action_item_id")
        batch_op.drop_column("meeting_note_id")

    op.drop_index("ix_meeting_notes_item_comments_created_at", table_name="meeting_notes_item_comments")
    op.drop_index("ix_meeting_notes_item_comments_action_item_id", table_name="meeting_notes_item_comments")
    op.drop_table("meeting_notes_item_comments")
    op.drop_table("meeting_notes_templates")
    op.drop_index("ix_meeting_notes_saved_views_user_id", table_name="meeting_notes_saved_views")
    op.drop_table("meeting_notes_saved_views")
    op.drop_table("meeting_notes_action_item_labels")
    op.drop_table("meeting_notes_labels")

    with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
        batch_op.drop_index("ix_meeting_notes_action_items_priority")
        batch_op.drop_column("ai_extracted")
        batch_op.drop_column("source_excerpt")
        batch_op.drop_column("priority")
