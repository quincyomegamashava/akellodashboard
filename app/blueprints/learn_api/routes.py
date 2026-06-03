"""Versioned JSON API for Learning Hub."""

from __future__ import annotations

from flask import jsonify, request

from app.blueprints.learn_api import bp
from app.learning_hub.auth import current_learner_id
from app.learning_hub.jobs import submit_coding_attempt
from app.learning_hub.models import LearnChallenge, LearnChallengeAttempt
from app.learning_hub.policy.unlock import challenge_visible_for_profile, learner_meets_challenge_prereqs


@bp.route("/health")
def health():
    return jsonify({"status": "ok", "service": "akello-learn", "api_version": "v1"})


@bp.route("/challenges")
def list_challenges():
    """Published challenges (filtered when learner session present)."""
    from app import db
    from app.learning_hub.models import LearnLearner

    learner_id = current_learner_id()
    learner = db.session.get(LearnLearner, learner_id) if learner_id else None

    cat_filter = request.args.get("category")
    q = LearnChallenge.query.filter_by(is_published=True).order_by(LearnChallenge.title)
    if cat_filter:
        q = q.filter(LearnChallenge.challenge_category == cat_filter)

    out = []
    for c in q.limit(100).all():
        if learner:
            if not challenge_visible_for_profile(
                c,
                category=learner.category,
                age_band=learner.age_band,
                skill_level=learner.skill_level,
            ):
                continue
            ok, _reasons = learner_meets_challenge_prereqs(learner.id, c)
            if not ok:
                continue
        out.append(
            {
                "id": c.id,
                "title": c.title,
                "challenge_category": c.challenge_category,
                "challenge_type": c.challenge_type,
                "difficulty": c.difficulty,
                "base_points": c.base_points,
            }
        )
    return jsonify({"items": out})


@bp.route("/attempts/<int:attempt_id>")
def attempt_status(attempt_id: int):
    """Poll grading status for a learner-owned attempt."""
    from app import db
    from app.learning_hub.models import LearnLearner

    learner_id = current_learner_id()
    if not learner_id:
        return jsonify({"error": "Unauthorized"}), 401

    attempt = db.session.get(LearnChallengeAttempt, attempt_id)
    if not attempt or attempt.learner_id != learner_id:
        return jsonify({"error": "Not found"}), 404

    return jsonify(
        {
            "id": attempt.id,
            "status": attempt.status,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "passed": attempt.passed,
            "xp_awarded": attempt.xp_awarded,
            "meta": attempt.meta_json,
        }
    )


@bp.route("/coding-submit", methods=["POST"])
def coding_submit_json():
    """Alternate JSON submit (CSRF exempt — pair with auth tokens / future API keys)."""
    learner_id = current_learner_id()
    if not learner_id:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    challenge_id = payload.get("challenge_id")
    code = payload.get("code") or ""
    try:
        cid = int(challenge_id)
    except (TypeError, ValueError):
        return jsonify({"error": "challenge_id required"}), 400

    try:
        attempt = submit_coding_attempt(
            learner_id=learner_id,
            challenge_id=cid,
            code=code,
            ip=request.remote_addr,
        )
        return jsonify({"attempt_id": attempt.id, "status": attempt.status}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
