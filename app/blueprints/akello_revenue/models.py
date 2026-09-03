"""Akello Revenue: fiscal periods and monthly revenue/subscriber metrics."""

from datetime import datetime

from app import db


class AkelloRevenuePeriod(db.Model):
    __tablename__ = "akello_revenue_periods"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    zig_usd_rate = db.Column(db.Numeric(12, 4), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    creator = db.relationship("User", foreign_keys=[created_by])
    months = db.relationship(
        "AkelloRevenueMonth",
        back_populates="period",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class AkelloRevenueMonth(db.Model):
    __tablename__ = "akello_revenue_months"
    __table_args__ = (
        db.UniqueConstraint("period_id", "month", name="uq_akello_revenue_period_month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(
        db.Integer,
        db.ForeignKey("akello_revenue_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month = db.Column(db.Integer, nullable=False)  # 1–12

    # Revenue: ASL/Library × HLF/Organic × USD/ZWL
    rev_asl_hlf_usd = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_asl_hlf_zwl = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_lib_hlf_usd = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_lib_hlf_zwl = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_asl_org_usd = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_asl_org_zwl = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_lib_org_usd = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    rev_lib_org_zwl = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    # Subscribers (same grid)
    sub_asl_hlf_usd = db.Column(db.Integer, nullable=False, default=0)
    sub_asl_hlf_zwl = db.Column(db.Integer, nullable=False, default=0)
    sub_lib_hlf_usd = db.Column(db.Integer, nullable=False, default=0)
    sub_lib_hlf_zwl = db.Column(db.Integer, nullable=False, default=0)
    sub_asl_org_usd = db.Column(db.Integer, nullable=False, default=0)
    sub_asl_org_zwl = db.Column(db.Integer, nullable=False, default=0)
    sub_lib_org_usd = db.Column(db.Integer, nullable=False, default=0)
    sub_lib_org_zwl = db.Column(db.Integer, nullable=False, default=0)

    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    period = db.relationship("AkelloRevenuePeriod", back_populates="months")
    updater = db.relationship("User", foreign_keys=[updated_by])
