"""Help Desk hub models: messages, attachments, macros, KB, CSAT.

HelpDeskTeam / watcher tables live in app.models so HelpDeskQuery mappers
can resolve before blueprints are imported.
"""

from datetime import datetime

from app import db
from app.models import HelpDeskTeam, helpdesk_team_members, helpdesk_watchers  # noqa: F401


class HelpDeskMessage(db.Model):
    __tablename__ = "helpdesk_messages"

    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(
        db.Integer,
        db.ForeignKey("helpdesk_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    author_name = db.Column(db.String(120), nullable=True)  # email sender display
    body = db.Column(db.Text, nullable=False, default="")
    is_internal = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    author = db.relationship("User", foreign_keys=[author_id])
    ticket = db.relationship(
        "HelpDeskQuery",
        backref=db.backref(
            "thread_messages",
            lazy="dynamic",
            cascade="all, delete-orphan",
            order_by="HelpDeskMessage.created_at",
        ),
    )


class HelpDeskAttachment(db.Model):
    __tablename__ = "helpdesk_attachments"

    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(
        db.Integer,
        db.ForeignKey("helpdesk_queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = db.Column(
        db.Integer,
        db.ForeignKey("helpdesk_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship(
        "HelpDeskQuery",
        backref=db.backref("attachments", lazy="dynamic", cascade="all, delete-orphan"),
    )
    message = db.relationship(
        "HelpDeskMessage",
        backref=db.backref("attachments", lazy="dynamic"),
    )


class HelpDeskMacro(db.Model):
    __tablename__ = "helpdesk_macros"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(40), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class HelpDeskArticle(db.Model):
    __tablename__ = "helpdesk_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, unique=True, index=True)
    body = db.Column(db.Text, nullable=False, default="")
    tags = db.Column(db.String(255), nullable=True)  # comma-separated
    published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class HelpDeskCSAT(db.Model):
    __tablename__ = "helpdesk_csat"

    id = db.Column(db.Integer, primary_key=True)
    query_id = db.Column(
        db.Integer,
        db.ForeignKey("helpdesk_queries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship(
        "HelpDeskQuery",
        backref=db.backref("csat", uselist=False, cascade="all, delete-orphan"),
    )
