"""Add source_item_id lineage on meeting action items."""

from alembic import op

from app.migration_schema import (
    add_column_if_missing,
    column_exists,
    create_index_if_missing,
    fk_exists,
    table_exists,
)


revision = "b1c2d3e4f5a6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def upgrade():
    bind = _bind()
    if not table_exists(bind, "meeting_notes_action_items"):
        return
    add_column_if_missing(
        bind,
        "meeting_notes_action_items",
        "source_item_id",
        "source_item_id INTEGER",
    )
    create_index_if_missing(
        bind,
        "ix_meeting_notes_action_items_source_item_id",
        "meeting_notes_action_items",
        ["source_item_id"],
    )
    with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
        if column_exists(bind, "meeting_notes_action_items", "source_item_id") and not fk_exists(
            bind, "meeting_notes_action_items", "fk_mn_action_source_item"
        ):
            batch_op.create_foreign_key(
                "fk_mn_action_source_item",
                "meeting_notes_action_items",
                ["source_item_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    bind = _bind()
    if not table_exists(bind, "meeting_notes_action_items"):
        return
    with op.batch_alter_table("meeting_notes_action_items", schema=None) as batch_op:
        if fk_exists(bind, "meeting_notes_action_items", "fk_mn_action_source_item"):
            batch_op.drop_constraint("fk_mn_action_source_item", type_="foreignkey")
        try:
            batch_op.drop_index("ix_meeting_notes_action_items_source_item_id")
        except Exception:
            pass
        if column_exists(bind, "meeting_notes_action_items", "source_item_id"):
            batch_op.drop_column("source_item_id")
