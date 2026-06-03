"""Parent / teacher guardian portal (separate session from learners)."""

from __future__ import annotations

from datetime import datetime

from flask import flash, g, redirect, render_template, request, url_for

from app import db
from app.blueprints.learn_guardian import bp
from app.learning_hub.auth import (
    attach_current_guardian,
    current_guardian_id,
    guardian_required,
    login_guardian,
    logout_guardian,
)
from app.learning_hub.models import LearnGuardianAccount, LearnLearner
from app.learning_hub.csrf_post_guard import require_csrf_on_post


@bp.before_request
def _attach_guardian_and_csrf():
    attach_current_guardian()
    require_csrf_on_post()


@bp.route("/")
def index():
    if current_guardian_id():
        return redirect(url_for("learn_guardian.dashboard"))
    return redirect(url_for("learn_guardian.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.guardian_account:
        return redirect(url_for("learn_guardian.dashboard"))

    if request.method != "POST":
        return render_template("learn/guardian/register.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    full_name = (request.form.get("full_name") or "").strip()
    role = (request.form.get("guardian_role") or "parent").strip()

    if not email or len(password) < 8:
        flash("Email and password (min 8 chars) required.", "danger")
        return render_template("learn/guardian/register.html"), 400

    if LearnGuardianAccount.query.filter_by(email=email).first():
        flash("Email already registered.", "danger")
        return render_template("learn/guardian/register.html"), 400

    g_acc = LearnGuardianAccount(email=email, full_name=full_name or email.split("@")[0], guardian_role=role)
    g_acc.set_password(password)
    db.session.add(g_acc)
    db.session.commit()
    login_guardian(g_acc.id)
    flash("Guardian account created.", "success")
    return redirect(url_for("learn_guardian.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.guardian_account:
        return redirect(url_for("learn_guardian.dashboard"))

    if request.method != "POST":
        return render_template("learn/guardian/login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    acc = LearnGuardianAccount.query.filter_by(email=email).first()
    if not acc or not acc.check_password(password):
        flash("Invalid credentials.", "danger")
        return render_template("learn/guardian/login.html"), 401

    login_guardian(acc.id)
    return redirect(url_for("learn_guardian.dashboard"))


@bp.route("/logout")
def logout():
    logout_guardian()
    flash("Signed out.", "info")
    return redirect(url_for("learn_guardian.login"))


@bp.route("/dashboard")
@guardian_required
def dashboard():
    acc = g.guardian_account
    learners = list(acc.learners)
    return render_template("learn/guardian/dashboard.html", guardian=acc, learners=learners)


@bp.route("/link", methods=["POST"])
@guardian_required
def link_child():
    username = (request.form.get("learner_username") or "").strip()
    code = (request.form.get("pairing_code") or "").strip().upper()

    learner = LearnLearner.query.filter_by(username=username).first()
    if not learner or not learner.pairing_code or learner.pairing_code.upper() != code:
        flash("Invalid learner username or pairing code.", "danger")
        return redirect(url_for("learn_guardian.dashboard"))

    if learner.pairing_expires_at and learner.pairing_expires_at < datetime.utcnow():
        flash("Pairing code expired — learner must generate a new one.", "warning")
        return redirect(url_for("learn_guardian.dashboard"))

    acc = g.guardian_account
    if learner not in acc.learners:
        acc.learners.append(learner)
    learner.pairing_code = None
    learner.pairing_expires_at = None
    db.session.commit()
    flash(f"Linked to learner @{username}.", "success")
    return redirect(url_for("learn_guardian.dashboard"))
