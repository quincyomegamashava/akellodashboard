"""Weekly meeting notes: meetings, focus rows, action items, assignees, activity log."""

from datetime import datetime

from app import db


meeting_notes_action_assignees = db.Table(
    "meeting_notes_action_assignees",
    db.Column(
        "action_item_id",
        db.Integer,
        db.ForeignKey("meeting_notes_action_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

meeting_notes_attendees = db.Table(
    "meeting_notes_attendees",
    db.Column(
        "meeting_note_id",
        db.Integer,
        db.ForeignKey("meeting_notes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

meeting_notes_action_item_labels = db.Table(
    "meeting_notes_action_item_labels",
    db.Column(
        "action_item_id",
        db.Integer,
        db.ForeignKey("meeting_notes_action_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "label_id",
        db.Integer,
        db.ForeignKey("meeting_notes_labels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

VALID_PRIORITIES = ("low", "medium", "high", "urgent")


class MeetingNote(db.Model):
    __tablename__ = "meeting_notes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="")
    meeting_date = db.Column(db.Date, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    meeting_time = db.Column(db.String(32), nullable=True)
    agenda = db.Column(db.Text, nullable=True)
    agenda_item_notes = db.Column(db.Text, nullable=True)
    guest_attendees = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    attendees = db.relationship(
        "User",
        secondary=meeting_notes_attendees,
        backref=db.backref("meeting_notes_attended", lazy="dynamic"),
    )
    focus_rows = db.relationship(
        "MeetingFocusRow",
        back_populates="meeting_note",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="MeetingFocusRow.sort_order",
    )


class MeetingFocusRow(db.Model):
    __tablename__ = "meeting_notes_focus_rows"

    id = db.Column(db.Integer, primary_key=True)
    meeting_note_id = db.Column(
        db.Integer,
        db.ForeignKey("meeting_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = db.Column(db.String(120), nullable=False, default="", index=True)
    focus_area = db.Column(db.Text, nullable=False, default="")
    discussion_notes = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    meeting_note = db.relationship("MeetingNote", back_populates="focus_rows")

    action_items = db.relationship(
        "MeetingActionItem",
        backref="focus_row",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="MeetingActionItem.sort_order",
    )


class MeetingActionItem(db.Model):
    __tablename__ = "meeting_notes_action_items"

    id = db.Column(db.Integer, primary_key=True)
    focus_row_id = db.Column(
        db.Integer,
        db.ForeignKey("meeting_notes_focus_rows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_to_action = db.Column(db.Text, nullable=False, default="")
    expected_impact = db.Column(db.Text, nullable=True)
    challenges = db.Column(db.Text, nullable=True)
    comments = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="open", index=True)
    priority = db.Column(db.String(16), nullable=False, default="medium", index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    start_date = db.Column(db.Date, nullable=True)
    source_excerpt = db.Column(db.Text, nullable=True)
    ai_extracted = db.Column(db.Boolean, nullable=False, default=False)
    carry_forward_count = db.Column(db.Integer, nullable=False, default=0)
    stakeholder_lead_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_stakeholder_leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    marketing_event_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    assignees = db.relationship(
        "User",
        secondary=meeting_notes_action_assignees,
        backref=db.backref("meeting_action_items_assigned", lazy="dynamic"),
    )
    labels = db.relationship(
        "MeetingLabel",
        secondary=meeting_notes_action_item_labels,
        backref=db.backref("action_items", lazy="dynamic"),
    )
    subtasks = db.relationship(
        "MeetingActionSubtask",
        back_populates="action_item",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="MeetingActionSubtask.sort_order",
    )


class MeetingActionSubtask(db.Model):
    __tablename__ = "meeting_notes_action_subtasks"

    id = db.Column(db.Integer, primary_key=True)
    action_item_id = db.Column(
        db.Integer,
        db.ForeignKey("meeting_notes_action_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(500), nullable=False, default="")
    is_done = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    assignee_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action_item = db.relationship("MeetingActionItem", back_populates="subtasks")
    assignee = db.relationship("User", foreign_keys=[assignee_user_id])


class MeetingNotesActivityLog(db.Model):
    __tablename__ = "meeting_notes_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    meeting_note_id = db.Column(
        db.Integer, db.ForeignKey("meeting_notes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    action = db.Column(db.String(32), nullable=False)
    entity_type = db.Column(db.String(64), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True)
    summary = db.Column(db.String(512), nullable=False, default="")
    details_json = db.Column(db.JSON, nullable=True)

    actor = db.relationship("User", foreign_keys=[actor_user_id])
    meeting_note = db.relationship("MeetingNote", foreign_keys=[meeting_note_id])


class MeetingLabel(db.Model):
    __tablename__ = "meeting_notes_labels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    color = db.Column(db.String(7), nullable=False, default="#64748b")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class MeetingSavedView(db.Model):
    __tablename__ = "meeting_notes_saved_views"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    filters_json = db.Column(db.JSON, nullable=False, default=dict)
    view_mode = db.Column(db.String(32), nullable=False, default="board")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


class MeetingTemplate(db.Model):
    __tablename__ = "meeting_notes_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    title_pattern = db.Column(db.String(255), nullable=False, default="")
    summary_template = db.Column(db.Text, nullable=True)
    focus_rows_json = db.Column(db.JSON, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])


class MeetingItemComment(db.Model):
    __tablename__ = "meeting_notes_item_comments"

    id = db.Column(db.Integer, primary_key=True)
    action_item_id = db.Column(
        db.Integer,
        db.ForeignKey("meeting_notes_action_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    author = db.relationship("User", foreign_keys=[author_user_id])
    action_item = db.relationship(
        "MeetingActionItem",
        backref=db.backref("comments_thread", lazy="dynamic", order_by="MeetingItemComment.created_at"),
    )


class MeetingDecision(db.Model):
    __tablename__ = "meeting_notes_decisions"

    id = db.Column(db.Integer, primary_key=True)
    meeting_note_id = db.Column(
        db.Integer,
        db.ForeignKey("meeting_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body = db.Column(db.Text, nullable=False, default="")
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    source_excerpt = db.Column(db.Text, nullable=True)
    decided_at = db.Column(db.Date, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    meeting_note = db.relationship("MeetingNote", backref=db.backref("decisions", lazy="dynamic"))
    owner = db.relationship("User", foreign_keys=[owner_user_id])
