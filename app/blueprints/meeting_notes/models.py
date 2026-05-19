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


class MeetingNote(db.Model):
    __tablename__ = "meeting_notes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="")
    meeting_date = db.Column(db.Date, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)
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
    due_date = db.Column(db.Date, nullable=True, index=True)
    start_date = db.Column(db.Date, nullable=True)
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
