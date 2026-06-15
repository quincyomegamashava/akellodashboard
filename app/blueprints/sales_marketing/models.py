"""Sales & Marketing: events, stakeholder leads, interest options, email campaigns."""

from datetime import datetime

from app import db


sales_marketing_event_attendees = db.Table(
    "sales_marketing_event_attendees",
    db.Column(
        "event_id",
        db.Integer,
        db.ForeignKey("sales_marketing_events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class MarketingEvent(db.Model):
    __tablename__ = "sales_marketing_events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active", index=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    attendees = db.relationship(
        "User",
        secondary=sales_marketing_event_attendees,
        backref=db.backref("marketing_events_attending", lazy="dynamic"),
    )
    leads = db.relationship(
        "StakeholderLead",
        back_populates="event",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class InterestOption(db.Model):
    __tablename__ = "sales_marketing_interest_options"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    leads = db.relationship("StakeholderLead", back_populates="interest_option", lazy="dynamic")


class StakeholderLead(db.Model):
    __tablename__ = "sales_marketing_stakeholder_leads"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    occupation = db.Column(db.String(255), nullable=False, default="")
    email = db.Column(db.String(255), nullable=False, index=True)
    mobile = db.Column(db.String(64), nullable=False, default="")
    school_name = db.Column(db.String(255), nullable=True)
    province = db.Column(db.String(120), nullable=True, index=True)
    organization = db.Column(db.String(255), nullable=True)
    role_category = db.Column(db.String(64), nullable=True)
    event_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    interest_option_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_interest_options.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    preferred_contact = db.Column(db.String(32), nullable=True)
    consent_marketing = db.Column(db.Boolean, nullable=False, default=False)
    comments = db.Column(db.Text, nullable=True)
    heard_about = db.Column(db.String(120), nullable=True)
    source = db.Column(db.String(64), nullable=False, default="public_form")
    is_duplicate_flag = db.Column(db.Boolean, nullable=False, default=False)
    duplicate_dismissed = db.Column(db.Boolean, nullable=False, default=False)
    follow_up_status = db.Column(db.String(32), nullable=False, default="new", index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    event = db.relationship("MarketingEvent", back_populates="leads")
    interest_option = db.relationship("InterestOption", back_populates="leads")
    creator = db.relationship("User", foreign_keys=[created_by])
    notes = db.relationship(
        "StakeholderLeadNote",
        back_populates="lead",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class StakeholderLeadNote(db.Model):
    __tablename__ = "sales_marketing_stakeholder_lead_notes"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_stakeholder_leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    lead = db.relationship("StakeholderLead", back_populates="notes")
    author = db.relationship("User", foreign_keys=[user_id])


class EmailCampaign(db.Model):
    __tablename__ = "sales_marketing_email_campaigns"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(500), nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    body_text = db.Column(db.Text, nullable=True)
    filter_snapshot = db.Column(db.JSON, nullable=True)
    recipient_count = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])
    recipients = db.relationship(
        "EmailCampaignRecipient",
        back_populates="campaign",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class EmailCampaignRecipient(db.Model):
    __tablename__ = "sales_marketing_email_campaign_recipients"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_email_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stakeholder_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_marketing_stakeholder_leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")
    error_message = db.Column(db.String(512), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)

    campaign = db.relationship("EmailCampaign", back_populates="recipients")
    stakeholder = db.relationship("StakeholderLead")


class PublicSubmissionRateLimit(db.Model):
    """Simple rate-limit counter for public form submissions."""

    __tablename__ = "sales_marketing_submission_rate_limits"

    id = db.Column(db.Integer, primary_key=True)
    ip_hash = db.Column(db.String(64), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
