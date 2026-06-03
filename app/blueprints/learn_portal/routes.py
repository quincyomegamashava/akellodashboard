"""Learner-facing Learning Hub pages."""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta

from flask import current_app, flash, g, redirect, render_template, request, send_from_directory, url_for

from app import db
from app.blueprints.learn_portal import bp
from app.learning_hub.auth import attach_current_learner, learner_required, login_learner, logout_learner
from app.learning_hub.jobs import submit_coding_attempt
from app.learning_hub.models import (
    LearnChallenge,
    LearnChallengeAttempt,
    LearnChallengeQuestion,
    LearnLearner,
    LearnLearnerTrackProgress,
    LearnLearningTrack,
    LearnQuestion,
    LearnQuestionOption,
)
from app.learning_hub.policy.unlock import challenge_visible_for_profile, learner_meets_challenge_prereqs
from app.learning_hub.services.quiz_grading import grade_quiz_challenge
from app.learning_hub.services.recommendation_engine import suggest_next_challenge_ids
from app.learning_hub.services.sandbox import grade_python_tests, sample_tests_for_challenge
from app.learning_hub.services.attempt_xp_policy import learner_already_has_prior_passing_attempt
from app.learning_hub.services.skill_level import refresh_learner_skill_level
from app.learning_hub.services.track_progress import refresh_all_tracks_for_learner, refresh_tracks_touching_challenge
from app.learning_hub.services.xp import compute_awarded_xp
from app.learning_hub.csrf_post_guard import require_csrf_on_post


@bp.before_request
def _attach_learner_and_csrf():
    attach_current_learner()
    require_csrf_on_post()


def _deny_if_challenge_inaccessible(learner: LearnLearner, challenge: LearnChallenge):
    """Return redirect response if learner cannot access challenge; else None."""
    if not challenge_visible_for_profile(
        challenge,
        category=learner.category,
        age_band=learner.age_band,
        skill_level=learner.skill_level,
    ):
        flash("This challenge is not available for your profile.", "warning")
        return redirect(url_for("learn_portal.challenges"))
    ok, reasons = learner_meets_challenge_prereqs(learner.id, challenge)
    if not ok:
        for r in reasons:
            flash(r, "warning")
        return redirect(url_for("learn_portal.challenges"))
    return None


def _coding_run_sample_url(challenge_id: int) -> str:
    """URL for Run sample POST (fallback path if endpoint not yet registered e.g. stale worker)."""
    try:
        return url_for("learn_portal.coding_challenge_run_sample", challenge_id=challenge_id)
    except Exception:
        return f"/learn/challenges/{challenge_id}/run-sample"


def _render_coding_challenge(
    challenge: LearnChallenge,
    starter_code: str,
    *,
    sample_result: dict | None = None,
    last_attempt: LearnChallengeAttempt | None = None,
):
    return render_template(
        "learn/challenge_coding.html",
        challenge=challenge,
        starter_code=starter_code,
        sample_result=sample_result,
        last_attempt=last_attempt,
        run_sample_url=_coding_run_sample_url(challenge.id),
    )


def _update_streak(learner: LearnLearner) -> None:
    today = date.today()
    if learner.last_activity_at:
        ld = learner.last_activity_at.date()
        if ld == today:
            return
        if ld == today - timedelta(days=1):
            learner.streak_days = (learner.streak_days or 0) + 1
        else:
            learner.streak_days = 1
    else:
        learner.streak_days = 1
    learner.last_activity_at = datetime.utcnow()


@bp.route("/")
def index():
    return render_template("learn/index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.learn_learner:
        return redirect(url_for("learn_portal.dashboard"))

    if request.method != "POST":
        return render_template("learn/register.html")

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    full_name = (request.form.get("full_name") or "").strip()
    category = (request.form.get("category") or "secondary").strip()
    age_band = (request.form.get("age_band") or "13-15").strip()
    skill_level = (request.form.get("skill_level") or "beginner").strip()

    if not username or not email or len(password) < 8:
        flash("Username, email, and password (min 8 chars) are required.", "danger")
        return render_template("learn/register.html"), 400

    if LearnLearner.query.filter((LearnLearner.username == username) | (LearnLearner.email == email)).first():
        flash("Username or email already registered.", "danger")
        return render_template("learn/register.html"), 400

    learner = LearnLearner(
        username=username,
        email=email,
        full_name=full_name or username,
        category=category,
        age_band=age_band,
        skill_level=skill_level,
    )
    learner.set_password(password)
    db.session.add(learner)
    db.session.commit()
    login_learner(learner.id)
    flash("Welcome to Akello Learn!", "success")
    return redirect(url_for("learn_portal.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.learn_learner:
        return redirect(url_for("learn_portal.dashboard"))

    if request.method != "POST":
        return render_template("learn/login.html")

    identifier = (request.form.get("identifier") or "").strip()
    password = request.form.get("password") or ""
    learner = LearnLearner.query.filter(
        (LearnLearner.username == identifier) | (LearnLearner.email == identifier.lower())
    ).first()
    if not learner or not learner.check_password(password) or not learner.is_active:
        flash("Invalid credentials.", "danger")
        return render_template("learn/login.html"), 401

    login_learner(learner.id)
    nxt = request.args.get("next") or url_for("learn_portal.dashboard")
    return redirect(nxt)


@bp.route("/logout")
def logout():
    logout_learner()
    flash("Signed out.", "info")
    return redirect(url_for("learn_portal.index"))


@bp.route("/dashboard")
@learner_required
def dashboard():
    learner = g.learn_learner
    suggestion_ids = suggest_next_challenge_ids(learner.id, limit=6)
    suggestion_challenges: list = []
    if suggestion_ids:
        found = LearnChallenge.query.filter(LearnChallenge.id.in_(suggestion_ids)).all()
        order = {cid: i for i, cid in enumerate(suggestion_ids)}
        suggestion_challenges = sorted(found, key=lambda c: order.get(c.id, 999))

    refresh_all_tracks_for_learner(learner.id)
    db.session.commit()

    tracks = LearnLearningTrack.query.filter_by(is_published=True).order_by(LearnLearningTrack.title).limit(12).all()
    progress_rows = LearnLearnerTrackProgress.query.filter_by(learner_id=learner.id).limit(6).all()
    return render_template(
        "learn/dashboard.html",
        learner=learner,
        suggestion_challenges=suggestion_challenges,
        tracks=tracks,
        progress_rows=progress_rows,
    )


@bp.route("/account/pairing-code", methods=["POST"])
@learner_required
def pairing_code_generate():
    learner = g.learn_learner
    code = secrets.token_hex(3).upper()
    learner.pairing_code = code
    learner.pairing_expires_at = datetime.utcnow() + timedelta(minutes=30)
    db.session.commit()
    flash(f"Give this code to your parent/teacher (expires in 30 min): {code}", "success")
    return redirect(url_for("learn_portal.dashboard"))


@bp.route("/sw.js")
def learn_service_worker():
    """Serve SW under /learn scope so learners get install/offline hooks."""
    import os

    static_root = current_app.static_folder or ""
    return send_from_directory(
        os.path.join(static_root, "learn"),
        "sw.js",
        mimetype="application/javascript",
        max_age=0,
    )


@bp.route("/challenges")
@learner_required
def challenges():
    learner = g.learn_learner
    q = LearnChallenge.query.filter_by(is_published=True).order_by(LearnChallenge.challenge_category, LearnChallenge.title)
    rows = []
    for c in q.all():
        if not challenge_visible_for_profile(
            c,
            category=learner.category,
            age_band=learner.age_band,
            skill_level=learner.skill_level,
        ):
            continue
        ok, reasons = learner_meets_challenge_prereqs(learner.id, c)
        rows.append({"challenge": c, "unlocked": ok, "reasons": reasons})
    return render_template("learn/challenges.html", rows=rows)


@bp.route(
    "/challenges/<int:challenge_id>/run-sample",
    methods=["POST"],
    endpoint="coding_challenge_run_sample",
)
@learner_required
def coding_challenge_run_sample(challenge_id: int):
    """Execute public/sample tests only — no XP, no attempt row."""
    learner = g.learn_learner
    challenge = LearnChallenge.query.filter_by(id=challenge_id, is_published=True).first_or_404()
    if challenge.challenge_type != "coding":
        flash("Not a coding challenge.", "warning")
        return redirect(url_for("learn_portal.challenges"))

    denied = _deny_if_challenge_inaccessible(learner, challenge)
    if denied:
        return denied

    content = challenge.content_json or {}
    code = (request.form.get("code") or "").strip()
    if not code:
        code = content.get("starter_code") or "# Write your Python below\n"

    sample_tests = sample_tests_for_challenge(content)
    if not sample_tests:
        flash("This challenge has no sample tests configured.", "warning")
        last = (
            LearnChallengeAttempt.query.filter_by(learner_id=learner.id, challenge_id=challenge.id)
            .order_by(LearnChallengeAttempt.id.desc())
            .first()
        )
        return _render_coding_challenge(challenge, code, sample_result=None, last_attempt=last)

    score, max_score, meta = grade_python_tests(code, sample_tests)
    all_pass = bool(max_score > 0 and score >= max_score - 1e-9)
    sample_result = {
        "kind": "sample",
        "score": score,
        "max_score": max_score,
        "all_pass": all_pass,
        "meta": meta,
    }
    if all_pass:
        flash("Sample tests passed — you can submit to run the full (hidden) suite.", "success")
    else:
        flash("Sample tests failed — fix your code before submitting.", "warning")

    last = (
        LearnChallengeAttempt.query.filter_by(learner_id=learner.id, challenge_id=challenge.id)
        .order_by(LearnChallengeAttempt.id.desc())
        .first()
    )
    return _render_coding_challenge(challenge, code, sample_result=sample_result, last_attempt=last)


@bp.route("/challenges/<int:challenge_id>", methods=["GET", "POST"])
@learner_required
def challenge_detail(challenge_id: int):
    learner = g.learn_learner
    challenge = LearnChallenge.query.filter_by(id=challenge_id, is_published=True).first_or_404()

    denied = _deny_if_challenge_inaccessible(learner, challenge)
    if denied:
        return denied

    # --- Coding challenges (sandbox / Judge0 / RQ) ---
    if challenge.challenge_type == "coding":
        content = challenge.content_json or {}
        starter = content.get("starter_code") or "# Write your Python below\n"

        if request.method == "POST":
            code = request.form.get("code") or ""
            try:
                attempt = submit_coding_attempt(
                    learner_id=learner.id,
                    challenge_id=challenge.id,
                    code=code,
                    ip=request.remote_addr,
                )
                if attempt.status == "graded":
                    if attempt.passed:
                        if attempt.xp_awarded and attempt.xp_awarded > 0:
                            flash(f"Passed tests. +{attempt.xp_awarded} XP", "success")
                        else:
                            flash(
                                "Passed tests — practice logged; XP was awarded on your first passing run for this challenge.",
                                "info",
                            )
                    else:
                        flash("Tests failed — check “Last submission” below for per-test details.", "warning")
                else:
                    flash("Submission queued — refresh in a moment if using background workers.", "info")
                refresh_learner_skill_level(learner.id)
                refresh_tracks_touching_challenge(learner.id, challenge.id)
                db.session.commit()
                return redirect(url_for("learn_portal.challenge_detail", challenge_id=challenge.id))
            except ValueError:
                flash("Invalid submission.", "danger")
                return redirect(url_for("learn_portal.challenges"))

        last_attempt = (
            LearnChallengeAttempt.query.filter_by(learner_id=learner.id, challenge_id=challenge.id)
            .order_by(LearnChallengeAttempt.id.desc())
            .first()
        )
        return _render_coding_challenge(challenge, starter, last_attempt=last_attempt)

    if challenge.challenge_type != "quiz":
        return render_template(
            "learn/challenge_placeholder.html",
            challenge=challenge,
            message="This challenge type is not playable in the browser yet.",
        )

    links = (
        LearnChallengeQuestion.query.filter_by(challenge_id=challenge.id)
        .order_by(LearnChallengeQuestion.sort_order)
        .all()
    )
    questions_payload = []
    for link in links:
        q = db.session.get(LearnQuestion, link.question_id)
        if not q:
            continue
        opts = LearnQuestionOption.query.filter_by(question_id=q.id).order_by(LearnQuestionOption.sort_order).all()
        questions_payload.append({"question": q, "options": opts, "points": link.points_override or 10})

    if not questions_payload:
        flash("This quiz has no questions yet. Ask an admin to attach questions.", "warning")
        return redirect(url_for("learn_portal.challenges"))

    if request.method == "POST":
        answers = {}
        for qentry in questions_payload:
            qid = str(qentry["question"].id)
            answers[qid] = request.form.get(f"q_{qid}")

        prior_attempts = (
            LearnChallengeAttempt.query.filter_by(learner_id=learner.id, challenge_id=challenge.id).count()
        )
        attempt_no = prior_attempts + 1

        score, max_score, _correct = grade_quiz_challenge(challenge.id, answers)
        passed = bool(max_score > 0 and score / max_score >= 0.6)

        ip = request.remote_addr or ""
        ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32] if ip else None

        prior_pass = learner_already_has_prior_passing_attempt(learner.id, challenge.id)
        eligible_for_credit = passed and not prior_pass

        first_attempt_bonus = bool(eligible_for_credit and attempt_no == 1)
        xp_awarded = 0
        if eligible_for_credit:
            xp_awarded = compute_awarded_xp(
                base_points=challenge.base_points,
                difficulty=challenge.difficulty,
                streak_days=learner.streak_days or 0,
                first_attempt_bonus=first_attempt_bonus,
            )

            learner.total_xp = int((learner.total_xp or 0) + xp_awarded)
            _update_streak(learner)

        attempt = LearnChallengeAttempt(
            learner_id=learner.id,
            challenge_id=challenge.id,
            attempt_no=attempt_no,
            submitted_at=datetime.utcnow(),
            time_spent_ms=None,
            score=score,
            max_score=max_score,
            passed=passed,
            payload_json={"answers": answers},
            status="graded",
            ip_hash=ip_hash,
            first_attempt_bonus_applied=first_attempt_bonus,
            xp_awarded=xp_awarded if eligible_for_credit else 0,
        )
        db.session.add(attempt)
        db.session.commit()

        refresh_learner_skill_level(learner.id)
        refresh_tracks_touching_challenge(learner.id, challenge.id)
        db.session.commit()

        if passed:
            if xp_awarded > 0:
                flash(f"First pass for credit: {score:.0f}/{max_score:.0f} pts. +{xp_awarded} XP", "success")
            else:
                flash(
                    f"Graded: {score:.0f}/{max_score:.0f} pts. Practice logged — XP was awarded on your first passing attempt.",
                    "info",
                )
        else:
            flash(f"Graded: {score:.0f}/{max_score:.0f} — keep practicing!", "warning")
        return redirect(url_for("learn_portal.challenge_detail", challenge_id=challenge.id))

    return render_template(
        "learn/challenge_quiz.html",
        challenge=challenge,
        questions_payload=questions_payload,
    )


@bp.route("/tracks")
@learner_required
def tracks():
    rows = LearnLearningTrack.query.filter_by(is_published=True).order_by(LearnLearningTrack.title).all()
    return render_template("learn/tracks.html", tracks=rows)


@bp.route("/tracks/<int:track_id>/enroll", methods=["POST"])
@learner_required
def track_enroll(track_id: int):
    learner = g.learn_learner
    track = LearnLearningTrack.query.filter_by(id=track_id, is_published=True).first_or_404()
    existing = LearnLearnerTrackProgress.query.filter_by(learner_id=learner.id, track_id=track.id).first()
    if existing:
        flash("Already enrolled.", "info")
        return redirect(url_for("learn_portal.tracks"))
    db.session.add(LearnLearnerTrackProgress(learner_id=learner.id, track_id=track.id, status="active"))
    db.session.commit()
    flash(f"Enrolled in {track.title}.", "success")
    return redirect(url_for("learn_portal.tracks"))


@bp.route("/leaderboard")
@learner_required
def leaderboard():
    top = LearnLearner.query.filter_by(is_active=True).order_by(LearnLearner.total_xp.desc()).limit(50).all()
    learner = g.learn_learner
    same_cat = (
        LearnLearner.query.filter_by(is_active=True, category=learner.category)
        .order_by(LearnLearner.total_xp.desc())
        .limit(50)
        .all()
    )
    return render_template("learn/leaderboard.html", global_rows=top, category_rows=same_cat, learner=learner)
