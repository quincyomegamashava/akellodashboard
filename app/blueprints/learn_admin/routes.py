"""Staff Learning Hub administration."""

from __future__ import annotations

from functools import wraps

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from app import db
from app.blueprints.learn_admin import bp
from app.learning_hub.admin_audit import log_staff_action
from app.learning_hub.seed_curriculum import seed_explorer_curriculum
from app.learning_hub.models import (
    LearnBadge,
    LearnChallenge,
    LearnChallengeAttempt,
    LearnChallengeQuestion,
    LearnLearner,
    LearnLearningTrack,
    LearnQuestion,
    LearnQuestionOption,
    LearnTrackChallenge,
)
from app.learning_hub.csrf_post_guard import require_csrf_on_post


def staff_learning_admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        role = getattr(current_user, "userRole", "") or ""
        if role != "Admin" and not current_user.has_privilege("Learning Hub Admin"):
            flash("Learning Hub admin access required.", "danger")
            return redirect(url_for("overview"))
        return fn(*args, **kwargs)

    return wrapper


@bp.before_request
def _learn_admin_csrf_on_post():
    require_csrf_on_post()


def _table_exists(name: str) -> bool:
    try:
        insp = sa_inspect(db.engine)
        return name in insp.get_table_names()
    except Exception:
        return False


def _seed_demo_content(actor_id: int | None) -> None:
    if LearnChallenge.query.filter_by(title="Demo: ICT fundamentals quiz").first():
        return

    badge = LearnBadge(
        slug="python-beginner",
        title="Python Beginner",
        description="Completed your first Python track milestone.",
    )
    db.session.add(badge)
    db.session.flush()

    q1 = LearnQuestion(
        stem="What does CPU stand for?",
        question_type="mcq",
        difficulty="beginner",
        explanation="Central Processing Unit executes instructions.",
    )
    q2 = LearnQuestion(
        stem="Which device is primarily for pointing and clicking?",
        question_type="mcq",
        difficulty="beginner",
        explanation="A mouse or trackpad moves the pointer.",
    )
    db.session.add_all([q1, q2])
    db.session.flush()

    o1 = [
        LearnQuestionOption(question_id=q1.id, text="Central Processing Unit", is_correct=True, sort_order=0),
        LearnQuestionOption(question_id=q1.id, text="Computer Personal Unit", is_correct=False, sort_order=1),
    ]
    o2 = [
        LearnQuestionOption(question_id=q2.id, text="Keyboard", is_correct=False, sort_order=0),
        LearnQuestionOption(question_id=q2.id, text="Mouse", is_correct=True, sort_order=1),
    ]
    db.session.add_all(o1 + o2)

    ch = LearnChallenge(
        title="Demo: ICT fundamentals quiz",
        description="Two quick questions to verify the quiz + XP flow.",
        challenge_category="ICT Fundamentals",
        challenge_type="quiz",
        difficulty="beginner",
        base_points=25,
        time_limit_seconds=300,
        suitable_categories=[],
        suitable_age_bands=[],
        suitable_skill_levels=[],
        instructions="Pick the best answer for each question.",
        is_published=True,
    )
    db.session.add(ch)
    db.session.flush()

    db.session.add_all(
        [
            LearnChallengeQuestion(challenge_id=ch.id, question_id=q1.id, sort_order=0, points_override=10),
            LearnChallengeQuestion(challenge_id=ch.id, question_id=q2.id, sort_order=1, points_override=10),
        ]
    )

    track = LearnLearningTrack(
        title="ICT Fundamentals Track",
        description="Start here — short intro path.",
        difficulty="beginner",
        category="ICT Fundamentals",
        estimated_duration_minutes=30,
        badge_reward_id=badge.id,
        suitable_age_bands=["9-12", "13-15", "16-18", "18+"],
        suitable_skill_levels=["beginner"],
        is_published=True,
    )
    db.session.add(track)
    db.session.flush()

    db.session.add(
        LearnTrackChallenge(
            track_id=track.id,
            challenge_id=ch.id,
            sort_order=0,
            unlock_after_challenge_id=None,
        )
    )

    log_staff_action(
        actor_staff_user_id=actor_id,
        action="learn_seed_demo",
        entity_type="learn_hub",
        entity_id=None,
        after={"challenge_id": ch.id, "track_id": track.id},
    )
    db.session.commit()


@bp.route("/")
@staff_learning_admin_required
def dashboard():
    learner_count = 0
    challenge_count = 0
    attempt_count = 0
    credit_completions = 0
    xp_awarded_rows = 0

    if _table_exists("learn_learners"):
        learner_count = db.session.scalar(text("SELECT COUNT(*) FROM learn_learners")) or 0
    if _table_exists("learn_challenges"):
        challenge_count = LearnChallenge.query.count()
    if _table_exists("learn_challenge_attempts"):
        attempt_count = LearnChallengeAttempt.query.count()
        xp_awarded_rows = LearnChallengeAttempt.query.filter(LearnChallengeAttempt.xp_awarded > 0).count()
        pairs = (
            db.session.query(LearnChallengeAttempt.learner_id, LearnChallengeAttempt.challenge_id)
            .filter(
                LearnChallengeAttempt.passed.is_(True),
                LearnChallengeAttempt.status == "graded",
            )
            .distinct()
            .all()
        )
        credit_completions = len(pairs)

    category_boards: dict[str, list] = {}
    if _table_exists("learn_learners"):
        raw_cats = db.session.query(LearnLearner.category).distinct().all()
        cat_list = sorted({c[0] for c in raw_cats if c[0]})
        if not cat_list:
            cat_list = ["primary", "secondary", "tertiary"]
        for cat in cat_list:
            category_boards[cat] = (
                LearnLearner.query.filter_by(is_active=True, category=cat)
                .order_by(LearnLearner.total_xp.desc())
                .limit(15)
                .all()
            )
    else:
        for cat in ("primary", "secondary", "tertiary"):
            category_boards[cat] = []

    return render_template(
        "learn/admin/dashboard.html",
        counts={
            "learners": learner_count,
            "challenges": challenge_count,
            "attempts": attempt_count,
            "credit_completions": credit_completions,
            "xp_awarded_rows": xp_awarded_rows,
        },
        category_boards=category_boards,
    )


@bp.route("/learners")
@staff_learning_admin_required
def learners_list():
    if not _table_exists("learn_learners"):
        flash("Learning Hub tables not migrated.", "warning")
        return render_template("learn/admin/learners_list.html", pagination=None)

    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = min(100, max(5, request.args.get("per_page", 25, type=int) or 25))
    q = LearnLearner.query.order_by(LearnLearner.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page)
    return render_template("learn/admin/learners_list.html", pagination=pagination)


@bp.route("/learners/<int:learner_id>")
@staff_learning_admin_required
def learner_detail(learner_id: int):
    if not _table_exists("learn_learners"):
        flash("Learning Hub tables not migrated.", "warning")
        return redirect(url_for("learn_admin.dashboard"))

    learner = LearnLearner.query.filter_by(id=learner_id).first_or_404()
    attempts = (
        LearnChallengeAttempt.query.filter_by(learner_id=learner.id)
        .order_by(LearnChallengeAttempt.submitted_at.desc().nullslast(), LearnChallengeAttempt.id.desc())
        .limit(150)
        .all()
    )
    cids = {a.challenge_id for a in attempts}
    challenges = {c.id: c for c in LearnChallenge.query.filter(LearnChallenge.id.in_(cids)).all()} if cids else {}
    return render_template(
        "learn/admin/learner_detail.html",
        learner=learner,
        attempts=attempts,
        challenges_by_id=challenges,
    )


@bp.route("/challenges")
@staff_learning_admin_required
def challenges_index():
    if not _table_exists("learn_challenges"):
        flash("Learning Hub tables not migrated.", "warning")
        return render_template("learn/admin/challenges_list.html", rows=[])

    challenges = LearnChallenge.query.order_by(LearnChallenge.challenge_category, LearnChallenge.title).all()
    rows = []
    for ch in challenges:
        aid = ch.id
        att_n = LearnChallengeAttempt.query.filter_by(challenge_id=aid).count() if _table_exists("learn_challenge_attempts") else 0
        pass_n = (
            LearnChallengeAttempt.query.filter_by(challenge_id=aid, passed=True).count()
            if _table_exists("learn_challenge_attempts")
            else 0
        )
        rows.append({"challenge": ch, "attempts": att_n, "passes": pass_n})
    return render_template("learn/admin/challenges_list.html", rows=rows)


@bp.route("/challenges/<int:challenge_id>")
@staff_learning_admin_required
def challenge_inspect(challenge_id: int):
    if not _table_exists("learn_challenges"):
        return redirect(url_for("learn_admin.dashboard"))

    ch = LearnChallenge.query.filter_by(id=challenge_id).first_or_404()
    attempt_n = LearnChallengeAttempt.query.filter_by(challenge_id=ch.id).count() if _table_exists("learn_challenge_attempts") else 0
    pass_n = (
        LearnChallengeAttempt.query.filter_by(challenge_id=ch.id, passed=True).count()
        if _table_exists("learn_challenge_attempts")
        else 0
    )
    recent = (
        LearnChallengeAttempt.query.filter_by(challenge_id=ch.id)
        .order_by(LearnChallengeAttempt.submitted_at.desc().nullslast(), LearnChallengeAttempt.id.desc())
        .limit(40)
        .all()
        if _table_exists("learn_challenge_attempts")
        else []
    )
    lids = {a.learner_id for a in recent}
    learners = {u.id: u for u in LearnLearner.query.filter(LearnLearner.id.in_(lids)).all()} if lids else {}
    return render_template(
        "learn/admin/challenge_detail.html",
        challenge=ch,
        attempt_n=attempt_n,
        pass_n=pass_n,
        recent_attempts=recent,
        learners_by_id=learners,
    )


@bp.route("/seed-explorer-curriculum", methods=["POST"])
@staff_learning_admin_required
def seed_explorer_curriculum_view():
    try:
        info = seed_explorer_curriculum(current_user.id)
        if info.get("skipped"):
            flash("Explorer curriculum already present.", "info")
        else:
            flash(f"Seeded Explorer path (track #{info.get('track_id')}).", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Seed failed: {exc}", "danger")
    return redirect(url_for("learn_admin.dashboard"))


@bp.route("/seed-demo", methods=["POST"])
@staff_learning_admin_required
def seed_demo():
    try:
        _seed_demo_content(current_user.id)
        flash("Demo track + quiz seeded (if not already present).", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Seed failed: {exc}", "danger")
    return redirect(url_for("learn_admin.dashboard"))


@bp.route("/challenges/new", methods=["GET", "POST"])
@staff_learning_admin_required
def challenge_new():
    if request.method != "POST":
        return render_template("learn/admin/challenge_form.html")

    title = (request.form.get("title") or "").strip()
    cat = (request.form.get("challenge_category") or "ICT Fundamentals").strip()
    ctype = (request.form.get("challenge_type") or "quiz").strip()
    diff = (request.form.get("difficulty") or "beginner").strip()
    pts = int(request.form.get("base_points") or 10)
    desc = (request.form.get("description") or "").strip()

    ch = LearnChallenge(
        title=title or "Untitled challenge",
        description=desc,
        challenge_category=cat,
        challenge_type=ctype,
        difficulty=diff,
        base_points=pts,
        is_published=True,
    )
    db.session.add(ch)
    db.session.flush()

    log_staff_action(
        actor_staff_user_id=current_user.id,
        action="learn_challenge_create",
        entity_type="learn_challenge",
        entity_id=ch.id,
        after={"title": ch.title},
    )
    db.session.commit()
    flash("Challenge created (add questions via seed or future editor).", "success")
    return redirect(url_for("learn_admin.dashboard"))
