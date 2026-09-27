"""Quiz Galaxy hub, shell play, catalog questions, and solo Caimex progression."""

from __future__ import annotations

import json
from datetime import datetime

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import app, db
from app.games.caimex_client import caimex_configured, generate_quiz_questions, suggest_next_progress
from app.games.galaxy_config import (
    GALAXY_WORLDS,
    catalog_subjects_for_world,
    world_by_shell,
    world_by_subject,
    worlds_for_hub_json,
)
from app.games.galaxy_questions import age_ranges_for_user, fetch_galaxy_questions, sanitize_quiz_text, shuffle_mcq_options
from app.models import AppSetting, Game, GameScore, GameUser, GalaxyProgress


GAMES_INCLUDE_CROSS_AGE_9_19_KEY = "games_include_cross_age_9_19"
TARGET_QUESTION_COUNT = 24


def _include_cross() -> bool:
    return (AppSetting.get_value(GAMES_INCLUDE_CROSS_AGE_9_19_KEY, "false") or "false").strip().lower() == "true"


def _resolve_world(shell: str | None = None, subject: str | None = None) -> dict | None:
    """Resolve planet from shell + subject. Prefer subject when it uses that shell."""
    subject = (subject or "").strip()
    shell = (shell or "").strip()
    by_subject = world_by_subject(subject) if subject else None
    by_shell = world_by_shell(shell) if shell else None
    if by_subject and by_shell:
        # Shared shells (e.g. rocket): subject picks the planet.
        # Mismatch (e.g. English subject + retrowave shell): trust the URL shell.
        if by_subject.get("shell") == by_shell.get("shell"):
            return by_subject
        return by_shell
    return by_subject or by_shell


def _shell_game(world: dict) -> Game | None:
    title = f"Galaxy — {world['name']}"
    return Game.query.filter_by(title=title, content_source="galaxy").first()


def _local_fallback_questions(subject: str, difficulty: str | None, count: int = 12) -> list[dict]:
    """Always-available MCQs so shells never start empty if catalog/AI fail."""
    sub = (subject or "General Knowledge").strip() or "General Knowledge"
    diff = (difficulty or "medium").strip().lower()
    bank = [
        (f"Which subject are you practising right now?", [sub, "Cooking only", "Driving only", "None of these"], 0),
        (f"A good way to learn {sub} is to…", ["Practise a little every day", "Never try questions", "Skip reading", "Guess forever"], 0),
        (f"If an answer is wrong in {sub}, you should…", ["Learn and try the next one", "Quit immediately", "Close your eyes", "Delete the quiz"], 0),
        (f"True or false: practise helps you improve at {sub}.", ["True", "False", "Never", "Only on Mondays"], 0),
        (f"Multiple-choice questions have…", ["Several options and one best answer", "No options", "Only pictures", "Only music"], 0),
        (f"When time is running in a quiz, you should…", ["Stay calm and think", "Panic and freeze", "Leave the page", "Ignore the question"], 0),
        (f"A streak means…", ["Several correct answers in a row", "You lost", "The game crashed", "Time stopped"], 0),
        (f"Difficulty '{diff}' means the questions are…", ["Matched to your level", "Impossible always", "Random nonsense", "Only for teachers"], 0),
        (f"Reading the question carefully in {sub} helps you…", ["Pick a better answer", "Waste time only", "Skip learning", "Lose points always"], 0),
        (f"After a quiz round you can…", ["Try again and improve", "Never play again", "Forget everything", "Break the timer"], 0),
        (f"Which is a healthy study habit?", ["Short focused practice", "No sleep before tests", "Never review mistakes", "Only copy friends"], 0),
        (f"In Akello Quiz Galaxy, correct answers…", ["Help you progress", "Delete your account", "Stop the sun", "Turn off sound forever"], 0),
    ]
    out = []
    for i, (prompt, options, ci) in enumerate(bank[: max(8, min(count, len(bank)))]):
        opts, new_ci = shuffle_mcq_options(options, ci)
        out.append({
            "id": f"fallback-{i}",
            "prompt": prompt,
            "options": opts,
            "correctIndex": new_ci,
            "explain": "Keep practising — you have got this!",
            "difficulty": diff,
            "subject": sub,
            "source": "fallback",
        })
    return out


def _prompt_key(q: dict | str | None) -> str:
    if isinstance(q, dict):
        return (q.get("prompt") or q.get("q") or "").strip().lower()
    return str(q or "").strip().lower()


def _collect_avoid_prompts(*sources: list | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for src in sources:
        if not src:
            continue
        for item in src:
            key = _prompt_key(item if isinstance(item, dict) else {"prompt": item})
            if key and key not in seen:
                seen.add(key)
                out.append(key)
    return out[:80]


def _build_question_pack(
    *,
    game_user: GameUser,
    catalog: list[str],
    ages: list[str],
    difficulty: str | None,
    level: int,
    limit: int,
    prefer_ai: bool = False,
    avoid_prompts: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Build a quiz pack. Level 2+ / prefer_ai leans on Caimex for fresh questions."""
    limit = max(12, min(60, int(limit or TARGET_QUESTION_COUNT)))
    level = max(1, int(level or 1))
    avoid = {_prompt_key({"prompt": p}) for p in (avoid_prompts or []) if p}
    avoid.discard("")

    questions: list[dict] = []
    ai_added = 0
    gk_count = 0

    # From level 2 (or explicit prefer_ai), generate most of the pack with Caimex.
    want_ai = prefer_ai or level >= 2
    if want_ai:
        need_ai = min(20, max(10, limit - 2))
        ai_qs = generate_quiz_questions(
            age=game_user.age,
            subject=catalog[0],
            difficulty=difficulty or "medium",
            level=level,
            count=need_ai,
            seed_examples=None,
            avoid_prompts=list(avoid)[:40],
        )
        for q in ai_qs:
            key = _prompt_key(q)
            if not key or key in avoid:
                continue
            questions.append(q)
            avoid.add(key)
            ai_added += 1

    # Fill remaining from catalog, skipping recently used prompts.
    need = max(0, limit - len(questions))
    if need > 0:
        catalog_qs = fetch_galaxy_questions(
            catalog_subjects=catalog,
            age_ranges=ages,
            difficulty=difficulty,
            limit=max(need * 3, limit),
            prefer_general_knowledge=True,
        )
        if len(catalog_qs) < need:
            wider = fetch_galaxy_questions(
                catalog_subjects=catalog,
                age_ranges=ages,
                difficulty=None,
                limit=max(need * 3, limit),
                prefer_general_knowledge=True,
            )
            seen = {_prompt_key(q) for q in catalog_qs}
            for q in wider:
                key = _prompt_key(q)
                if key and key not in seen:
                    catalog_qs.append(q)
                    seen.add(key)

        for q in catalog_qs:
            key = _prompt_key(q)
            if not key or key in avoid:
                continue
            questions.append(q)
            avoid.add(key)
            if (q.get("source") or "") == "general_knowledge":
                gk_count += 1
            if len(questions) >= limit:
                break

    # If still short (Caimex down / thin catalog), try another AI pass then fallbacks.
    if len(questions) < max(8, limit // 2) and caimex_configured():
        extra_need = max(0, limit - len(questions))
        if extra_need > 0:
            more = generate_quiz_questions(
                age=game_user.age,
                subject=catalog[0],
                difficulty=difficulty or "medium",
                level=level,
                count=min(20, extra_need),
                avoid_prompts=list(avoid)[:40],
            )
            for q in more:
                key = _prompt_key(q)
                if not key or key in avoid:
                    continue
                questions.append(q)
                avoid.add(key)
                ai_added += 1
                if len(questions) >= limit:
                    break

    if len(questions) < 8:
        for q in _local_fallback_questions(catalog[0], difficulty, count=12):
            key = _prompt_key(q)
            if key in avoid and len(questions) >= 8:
                continue
            questions.append(q)
            if key:
                avoid.add(key)
            if len(questions) >= limit:
                break

    for q in questions:
        if not isinstance(q, dict):
            continue
        if "prompt" in q:
            q["prompt"] = sanitize_quiz_text(q.get("prompt"))
        if "explain" in q:
            q["explain"] = sanitize_quiz_text(q.get("explain"))
        opts = q.get("options")
        if isinstance(opts, list) and len(opts) >= 2:
            shuffled, ci = shuffle_mcq_options(opts, q.get("correctIndex", 0))
            q["options"] = shuffled
            q["correctIndex"] = ci

    meta = {
        "general_knowledge_count": gk_count,
        "ai_count": ai_added,
        "catalog_count": max(0, len(questions) - ai_added),
        "fallback_used": any((q.get("source") == "fallback") for q in questions),
        "prefer_ai": want_ai,
        "avoided": len(avoid_prompts or []),
    }
    return questions[:limit], meta


def _persist_session(row: GalaxyProgress | None, status: str, payload: dict | None) -> None:
    if row is None:
        return
    try:
        if hasattr(row, "session_status"):
            row.session_status = status
        if hasattr(row, "session_json"):
            row.session_json = json.dumps(payload) if payload is not None else None
        row.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()


def _parse_session(row: GalaxyProgress | None) -> dict | None:
    if not row:
        return None
    raw = getattr(row, "session_json", None)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (TypeError, json.JSONDecodeError):
        return None


def _get_or_create_progress(user_id: int, subject: str, shell: str) -> GalaxyProgress | None:
    try:
        row = GalaxyProgress.query.filter_by(
            game_user_id=user_id, subject=subject, shell=shell
        ).first()
        if row:
            return row
        row = GalaxyProgress(
            game_user_id=user_id,
            subject=subject,
            shell=shell,
            level=1,
            difficulty="medium",
        )
        db.session.add(row)
        db.session.flush()
        return row
    except Exception:
        db.session.rollback()
        return None


@app.route("/quiz-galaxy")
def quiz_galaxy():
    return render_template(
        "quiz_galaxy.html",
        title="Akello Quiz Galaxy",
        worlds=worlds_for_hub_json(),
    )


@app.route("/play-galaxy/<shell>")
def play_galaxy(shell):
    subject = (request.args.get("subject") or "").strip()
    world = _resolve_world(shell=shell, subject=subject)
    if not world or (world.get("kind") or "subject") == "hub":
        return redirect(url_for("quiz_galaxy"))
    catalog = catalog_subjects_for_world(world, subject or None)
    primary_subject = world.get("label") or (catalog[0] if catalog else "")
    game = _shell_game(world)
    return render_template(
        "play_galaxy.html",
        title=world["name"],
        world=world,
        shell=world["shell"],
        subject=primary_subject,
        catalog_subjects=catalog,
        shell_game_id=game.id if game else None,
        shell_static_url=url_for("static", filename=f"games/galaxy/{world['shell']}/index.html"),
    )


@app.route("/api/galaxy/worlds", methods=["GET"])
def api_galaxy_worlds():
    return jsonify({"worlds": worlds_for_hub_json()}), 200


def _can_manage_galaxy() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    return (
        getattr(current_user, "userRole", None) == "Admin"
        or (hasattr(current_user, "has_privilege") and (
            current_user.has_privilege("Akello Events")
            or current_user.has_privilege("Content Development")
        ))
    )


@app.route("/api/galaxy/admin/shells", methods=["GET"])
@login_required
def api_galaxy_admin_shells():
    """Staff view of Quiz Galaxy worlds + whether shell Game rows are seeded."""
    if not _can_manage_galaxy():
        return jsonify({"error": "Unauthorized"}), 403
    rows = []
    for w in GALAXY_WORLDS:
        kind = w.get("kind") or "subject"
        if kind == "hub":
            continue
        title = f"Galaxy — {w['name']}"
        game = Game.query.filter_by(title=title, content_source="galaxy").first()
        rows.append({
            "id": w["id"],
            "label": w["label"],
            "name": w["name"],
            "shell": w["shell"],
            "kind": kind,
            "catalog_subjects": w.get("catalog_subjects") or [],
            "play_path": f"/play-galaxy/{w['shell']}?subject={w['label']}",
            "preview_key": w.get("preview_key"),
            "seeded": game is not None,
            "game_id": game.id if game else None,
            "is_active": bool(game.is_active) if game else False,
            "max_score": game.max_score if game else None,
        })
    return jsonify({
        "shells": rows,
        "counts": {
            "total": len(rows),
            "subject": sum(1 for r in rows if r["kind"] == "subject"),
            "challenge": sum(1 for r in rows if r["kind"] == "challenge"),
            "seeded": sum(1 for r in rows if r["seeded"]),
        },
    }), 200


@app.route("/api/galaxy/admin/seed", methods=["POST"])
@login_required
def api_galaxy_admin_seed():
    """Upsert Game rows for every Quiz Galaxy shell (subject + challenge)."""
    if not _can_manage_galaxy():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        from app.games.seed_galaxy_games import seed_galaxy_shell_games
        result = seed_galaxy_shell_games()
        return jsonify({"ok": True, **result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/galaxy/admin/scores", methods=["GET"])
@login_required
def api_galaxy_admin_scores():
    """Leaderboard + recent attempts + progress for Quiz Galaxy shells."""
    if not _can_manage_galaxy():
        return jsonify({"error": "Unauthorized"}), 403

    shell = (request.args.get("shell") or "").strip()
    game_id = request.args.get("game_id", type=int)
    limit = request.args.get("limit", default=40, type=int)
    limit = max(5, min(100, int(limit or 40)))

    galaxy_games = Game.query.filter_by(content_source="galaxy").all()
    game_by_id = {g.id: g for g in galaxy_games}
    shell_to_game: dict[str, Game] = {}
    for w in GALAXY_WORLDS:
        if (w.get("kind") or "subject") == "hub":
            continue
        title = f"Galaxy — {w['name']}"
        for g in galaxy_games:
            if g.title == title:
                shell_to_game[w["shell"]] = g
                break

    selected_game = None
    if game_id and game_id in game_by_id:
        selected_game = game_by_id[game_id]
    elif shell and shell in shell_to_game:
        selected_game = shell_to_game[shell]

    game_ids = [selected_game.id] if selected_game else list(game_by_id.keys())

    leaderboard = []
    recent = []
    if game_ids:
        scores = (
            GameScore.query.filter(GameScore.game_id.in_(game_ids))
            .order_by(GameScore.played_at.desc())
            .limit(800)
            .all()
        )
        user_ids = {s.game_user_id for s in scores}
        users = {
            u.id: u
            for u in GameUser.query.filter(GameUser.id.in_(user_ids)).all()
        } if user_ids else {}

        best_by_user: dict[tuple[int, int], dict] = {}
        for s in scores:
            key = (s.game_user_id, s.game_id)
            pct = float(s.percentage) if s.percentage is not None else (
                (float(s.score) / float(s.max_score) * 100.0) if s.max_score else 0.0
            )
            prev = best_by_user.get(key)
            if prev is None or float(s.score or 0) > prev["score"] or (
                float(s.score or 0) == prev["score"] and pct > prev["percentage"]
            ):
                u = users.get(s.game_user_id)
                g = game_by_id.get(s.game_id)
                best_by_user[key] = {
                    "game_user_id": s.game_user_id,
                    "username": (u.username if u else None) or f"user-{s.game_user_id}",
                    "display_name": (
                        f"{(u.firstname or '').strip()} {(u.surname or '').strip()}".strip()
                        if u else ""
                    ) or None,
                    "age": u.age if u else None,
                    "game_id": s.game_id,
                    "game_title": g.title if g else None,
                    "score": int(s.score or 0),
                    "max_score": int(s.max_score or 0) if s.max_score is not None else None,
                    "percentage": round(pct, 1),
                    "attempts": 0,
                    "last_played": s.played_at.isoformat() + "Z" if s.played_at else None,
                }

        attempt_counts: dict[tuple[int, int], int] = {}
        for s in scores:
            key = (s.game_user_id, s.game_id)
            attempt_counts[key] = attempt_counts.get(key, 0) + 1
        for key, row in best_by_user.items():
            row["attempts"] = attempt_counts.get(key, 1)

        leaderboard = sorted(
            best_by_user.values(),
            key=lambda r: (-r["score"], -r["percentage"], r["username"] or ""),
        )[:limit]

        for s in scores[:limit]:
            u = users.get(s.game_user_id)
            g = game_by_id.get(s.game_id)
            pct = float(s.percentage) if s.percentage is not None else (
                (float(s.score) / float(s.max_score) * 100.0) if s.max_score else 0.0
            )
            recent.append({
                "id": s.id,
                "game_user_id": s.game_user_id,
                "username": (u.username if u else None) or f"user-{s.game_user_id}",
                "display_name": (
                    f"{(u.firstname or '').strip()} {(u.surname or '').strip()}".strip()
                    if u else ""
                ) or None,
                "game_id": s.game_id,
                "game_title": g.title if g else None,
                "score": int(s.score or 0),
                "max_score": int(s.max_score or 0) if s.max_score is not None else None,
                "percentage": round(pct, 1),
                "attempt_number": s.attempt_number,
                "played_at": s.played_at.isoformat() + "Z" if s.played_at else None,
            })

    progress_q = GalaxyProgress.query.order_by(GalaxyProgress.updated_at.desc())
    if shell:
        progress_q = progress_q.filter_by(shell=shell)
    elif selected_game:
        # Map game title back to shell
        for sh, g in shell_to_game.items():
            if g.id == selected_game.id:
                progress_q = progress_q.filter_by(shell=sh)
                break
    progress_rows = progress_q.limit(limit).all()
    p_user_ids = {r.game_user_id for r in progress_rows}
    p_users = {
        u.id: u
        for u in GameUser.query.filter(GameUser.id.in_(p_user_ids)).all()
    } if p_user_ids else {}
    progress = []
    for r in progress_rows:
        u = p_users.get(r.game_user_id)
        progress.append({
            "game_user_id": r.game_user_id,
            "username": (u.username if u else None) or f"user-{r.game_user_id}",
            "display_name": (
                f"{(u.firstname or '').strip()} {(u.surname or '').strip()}".strip()
                if u else ""
            ) or None,
            "subject": r.subject,
            "shell": r.shell,
            "level": r.level,
            "difficulty": r.difficulty,
            "session_status": getattr(r, "session_status", None) or "idle",
            "coaching_blurb": r.coaching_blurb,
            "updated_at": r.updated_at.isoformat() + "Z" if r.updated_at else None,
        })

    shells_meta = []
    for w in GALAXY_WORLDS:
        if (w.get("kind") or "subject") == "hub":
            continue
        g = shell_to_game.get(w["shell"])
        shells_meta.append({
            "shell": w["shell"],
            "name": w["name"],
            "label": w["label"],
            "kind": w.get("kind") or "subject",
            "game_id": g.id if g else None,
        })

    return jsonify({
        "filter": {
            "shell": shell or None,
            "game_id": selected_game.id if selected_game else None,
            "game_title": selected_game.title if selected_game else None,
        },
        "shells": shells_meta,
        "leaderboard": leaderboard,
        "recent": recent,
        "progress": progress,
        "counts": {
            "leaderboard": len(leaderboard),
            "recent": len(recent),
            "progress": len(progress),
        },
    }), 200


@app.route("/api/galaxy/questions", methods=["GET"])
def api_galaxy_questions():
    user_id = request.args.get("user_id", type=int)
    shell = (request.args.get("shell") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    difficulty = (request.args.get("difficulty") or "").strip().lower() or None
    limit = request.args.get("limit", default=TARGET_QUESTION_COUNT, type=int)
    fresh = (request.args.get("fresh") or "").strip().lower() in ("1", "true", "yes")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    game_user = GameUser.query.get(user_id)
    if not game_user:
        return jsonify({"error": "User not found"}), 404

    world = _resolve_world(shell=shell, subject=subject)
    if world is None:
        return jsonify({"error": "Unknown shell or subject"}), 400

    catalog = catalog_subjects_for_world(world, subject or None)
    ages = age_ranges_for_user(game_user, _include_cross())
    progress = _get_or_create_progress(game_user.id, catalog[0], world["shell"])
    level = (progress.level if progress else 1) or 1
    level_override = request.args.get("level", type=int)
    if level_override and level_override >= 1:
        # Replay a specific cleared/failed level without changing saved progress.
        level = level_override

    if not difficulty:
        difficulty = (progress.difficulty if progress else None) or "medium"

    session = _parse_session(progress)
    session_status = getattr(progress, "session_status", None) if progress else None
    if (
        not fresh
        and (session_status or "") == "in_progress"
        and session
        and isinstance(session.get("questions"), list)
        and len(session["questions"]) >= 2
    ):
        return jsonify({
            "shell": world["shell"],
            "subject": catalog[0],
            "catalog_subjects": catalog,
            "difficulty": difficulty,
            "level": level,
            "questions": session["questions"],
            "count": len(session["questions"]),
            "resume": True,
            "session": {
                "asked": session.get("asked", 0),
                "playerCorrect": session.get("playerCorrect", 0),
                "rivalCorrect": session.get("rivalCorrect", 0),
                "playerStep": session.get("playerStep", 0),
                "rivalStep": session.get("rivalStep", 0),
                "streak": session.get("streak", 0),
                "secondsLeft": session.get("secondsLeft"),
                "deck": session.get("deck") or [],
                "status": "in_progress",
            },
            "sources": session.get("sources") or {},
        }), 200

    # Prefer Caimex for level-ups / fresh packs so learners don't see the same bank again.
    prefer_ai = fresh or level >= 2
    avoid_prompts = _collect_avoid_prompts(
        (session or {}).get("questions") if isinstance(session, dict) else None,
        (session or {}).get("last_prompts") if isinstance(session, dict) else None,
    )

    questions, sources = _build_question_pack(
        game_user=game_user,
        catalog=catalog,
        ages=ages,
        difficulty=difficulty,
        level=level,
        limit=limit,
        prefer_ai=prefer_ai,
        avoid_prompts=avoid_prompts,
    )

    _persist_session(progress, "in_progress", {
        "questions": questions,
        "asked": 0,
        "playerCorrect": 0,
        "rivalCorrect": 0,
        "playerStep": 0,
        "rivalStep": 0,
        "streak": 0,
        "secondsLeft": None,
        "deck": [],
        "sources": sources,
        "last_prompts": avoid_prompts[:60] + [
            _prompt_key(q) for q in questions if _prompt_key(q)
        ][:40],
        "pack_level": level,
        "status": "in_progress",
    })

    return jsonify({
        "shell": world["shell"],
        "subject": catalog[0],
        "catalog_subjects": catalog,
        "difficulty": difficulty,
        "level": level,
        "questions": questions,
        "count": len(questions),
        "resume": False,
        "session": None,
        "sources": sources,
    }), 200


@app.route("/api/galaxy/session", methods=["POST"])
def api_galaxy_session_save():
    """Checkpoint mid-round progress so the learner can continue later."""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    shell = (data.get("shell") or "").strip()
    subject = (data.get("subject") or "").strip()
    if not user_id or not shell:
        return jsonify({"error": "user_id and shell are required"}), 400

    world = _resolve_world(shell=shell, subject=subject)
    if not world:
        return jsonify({"error": "Unknown shell"}), 400
    catalog = catalog_subjects_for_world(world, subject or None)
    sub = catalog[0]
    row = _get_or_create_progress(int(user_id), sub, world["shell"])

    existing = _parse_session(row) or {}
    questions = data.get("questions")
    if not isinstance(questions, list):
        questions = existing.get("questions") or []

    payload = {
        "questions": questions,
        "asked": int(data.get("asked") or existing.get("asked") or 0),
        "playerCorrect": int(data.get("playerCorrect") or 0),
        "rivalCorrect": int(data.get("rivalCorrect") or 0),
        "playerStep": int(data.get("playerStep") or 0),
        "rivalStep": int(data.get("rivalStep") or 0),
        "streak": int(data.get("streak") or 0),
        "secondsLeft": data.get("secondsLeft"),
        "deck": data.get("deck") if isinstance(data.get("deck"), list) else (existing.get("deck") or []),
        "sources": existing.get("sources") or {},
        "status": "in_progress",
    }
    _persist_session(row, "in_progress", payload)
    return jsonify({"success": True, "session_status": "in_progress"}), 200


@app.route("/api/galaxy/classic-games", methods=["GET"])
def api_galaxy_classic_games():
    """Classic catalog quizzes for a subject planet (excludes galaxy shell rows)."""
    user_id = request.args.get("user_id", type=int)
    subject = (request.args.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "subject is required"}), 400

    world = world_by_subject(subject)
    catalog = [subject]
    if world:
        catalog = catalog_subjects_for_world(world, subject)

    ages: list[str] | None = None
    if user_id:
        game_user = GameUser.query.get(user_id)
        if not game_user:
            return jsonify({"error": "User not found"}), 404
        ages = age_ranges_for_user(game_user, _include_cross())

    q = Game.query.filter(
        Game.is_active.is_(True),
        Game.subject.in_(catalog),
        db.or_(Game.content_source.is_(None), Game.content_source != "galaxy"),
    )
    if ages:
        q = q.filter(Game.age_range.in_(ages))

    all_games = q.order_by(Game.title.asc()).all()
    gk_games = [g for g in all_games if (getattr(g, "content_source", None) or "general_knowledge") == "general_knowledge"]
    games = gk_games if gk_games else all_games

    from app.games.quiz_titles import display_game_title

    return jsonify({
        "subject": catalog[0],
        "catalog_subjects": catalog,
        "games": [{
            "id": g.id,
            "title": display_game_title(
                g.title,
                content_source=getattr(g, "content_source", None),
                grade=getattr(g, "grade", None),
            ),
            "description": g.description,
            "age_range": g.age_range,
            "subject": g.subject,
            "grade": getattr(g, "grade", None),
            "content_source": getattr(g, "content_source", None) or "general_knowledge",
            "max_score": g.max_score,
            "difficulty_level": g.difficulty_level,
            "solo_theme": getattr(g, "solo_theme", None) or "swim",
            "play_path": f"/play-game/{g.id}",
        } for g in games],
        "count": len(games),
    }), 200


@app.route("/api/galaxy/learner-summary", methods=["GET"])
def api_galaxy_learner_summary():
    """XP/streak + per-subject galaxy levels for Mission Control / planet rings."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    game_user = GameUser.query.get(user_id)
    if not game_user:
        return jsonify({"error": "User not found"}), 404

    scores = GameScore.query.filter_by(game_user_id=user_id).all()
    total_score = sum(int(s.score or 0) for s in scores)
    total_games = len({s.game_id for s in scores})
    best = max((int(s.score or 0) for s in scores), default=0)
    xp = total_score
    level = (xp // 1000) + 1
    into = xp % 1000
    streak_days = 1 if scores else 0

    rows = GalaxyProgress.query.filter_by(game_user_id=user_id).all()
    subjects = []
    for row in rows:
        subjects.append({
            "subject": row.subject,
            "shell": row.shell,
            "level": row.level or 1,
            "difficulty": row.difficulty or "medium",
            "can_resume": (getattr(row, "session_status", None) or "") == "in_progress",
            "coaching_blurb": row.coaching_blurb,
        })

    name = f"{(game_user.firstname or '').strip()} {(game_user.surname or '').strip()}".strip() or game_user.username

    return jsonify({
        "user": {
            "id": game_user.id,
            "username": game_user.username,
            "name": name,
            "age": game_user.age,
        },
        "xp": {
            "total": xp,
            "level": level,
            "into_level": into,
            "to_next": 1000,
            "pct": min(100, int(into / 10)),
        },
        "stats": {
            "total_games": total_games,
            "best_score": best,
            "attempts": len(scores),
            "streak_days": streak_days,
        },
        "subjects": subjects,
    }), 200


@app.route("/api/galaxy/progress", methods=["GET"])
def api_galaxy_progress_get():
    user_id = request.args.get("user_id", type=int)
    shell = (request.args.get("shell") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    if not user_id or not shell:
        return jsonify({"error": "user_id and shell are required"}), 400
    world = _resolve_world(shell=shell, subject=subject)
    if not world:
        return jsonify({"error": "Unknown shell"}), 400
    catalog = catalog_subjects_for_world(world, subject or None)
    sub = catalog[0]
    row = GalaxyProgress.query.filter_by(
        game_user_id=user_id, subject=sub, shell=world["shell"]
    ).first()
    if not row:
        return jsonify({
            "level": 1,
            "difficulty": "medium",
            "coaching_blurb": None,
            "subject": sub,
            "shell": world["shell"],
            "session_status": "idle",
            "can_resume": False,
        }), 200
    return jsonify({
        "level": row.level,
        "difficulty": row.difficulty,
        "coaching_blurb": row.coaching_blurb,
        "subject": row.subject,
        "shell": row.shell,
        "session_status": row.session_status or "idle",
        "can_resume": (row.session_status or "") == "in_progress",
    }), 200


@app.route("/api/galaxy/complete", methods=["POST"])
def api_galaxy_complete():
    """Submit solo shell score + update Caimex-driven level/difficulty (not for races)."""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    shell = (data.get("shell") or "").strip()
    subject = (data.get("subject") or "").strip()
    score = data.get("score")
    max_score = data.get("max_score")

    if not user_id or score is None:
        return jsonify({"error": "user_id and score are required"}), 400
    game_user = GameUser.query.get(int(user_id))
    if not game_user:
        return jsonify({"error": "User not found"}), 404

    world = _resolve_world(shell=shell, subject=subject)
    if not world:
        return jsonify({"error": "Unknown shell"}), 400
    catalog = catalog_subjects_for_world(world, subject or None)
    sub = catalog[0]

    game = _shell_game(world)
    if not game:
        try:
            from app.games.seed_galaxy_games import seed_galaxy_shell_games
            seed_galaxy_shell_games()
            game = _shell_game(world)
        except Exception:
            pass
    if not game:
        return jsonify({"error": "Galaxy shell game not seeded"}), 500

    try:
        score_i = int(score)
        max_i = int(max_score) if max_score is not None else (game.max_score or 20)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid score"}), 400

    pct = (score_i / max_i * 100.0) if max_i else 0.0
    last = (
        GameScore.query.filter_by(game_user_id=game_user.id, game_id=game.id)
        .order_by(GameScore.attempt_number.desc())
        .first()
    )
    attempt = (last.attempt_number + 1) if last else 1
    gs = GameScore(
        game_user_id=game_user.id,
        game_id=game.id,
        score=score_i,
        max_score=max_i,
        percentage=pct,
        attempt_number=attempt,
    )
    db.session.add(gs)

    row = _get_or_create_progress(game_user.id, sub, world["shell"])
    cur_level = (row.level if row else 1) or 1
    cur_diff = (row.difficulty if row else None) or "medium"

    suggestion = suggest_next_progress(
        age=game_user.age,
        subject=sub,
        shell=world["shell"],
        current_level=cur_level,
        current_difficulty=cur_diff,
        score_pct=pct,
    )

    # Candy Crush style: clear (>=70%) unlocks next level; otherwise replay same level.
    passed = bool(suggestion.get("passed")) or pct >= 70
    if passed:
        next_level = max(int(suggestion.get("next_level") or cur_level), cur_level + 1)
    else:
        next_level = cur_level
    suggestion["next_level"] = next_level
    suggestion["passed"] = passed

    if row is not None:
        prior = _parse_session(row) or {}
        used_prompts = _collect_avoid_prompts(
            prior.get("questions") if isinstance(prior.get("questions"), list) else None,
            prior.get("last_prompts") if isinstance(prior.get("last_prompts"), list) else None,
        )
        row.level = next_level
        row.difficulty = suggestion["difficulty"]
        row.coaching_blurb = suggestion.get("coaching_blurb")
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Keep seen prompts so the next level pack can avoid repeats via Caimex.
        _persist_session(row, "idle", {
            "last_prompts": used_prompts[:80],
            "last_level": cur_level,
            "played_level": cur_level,
            "next_level": next_level,
            "passed": passed,
            "status": "idle",
        })

    return jsonify({
        "success": True,
        "passed": passed,
        "played_level": cur_level,
        "next_level": next_level,
        "score": {
            "id": gs.id,
            "score": gs.score,
            "max_score": gs.max_score,
            "percentage": gs.percentage,
            "attempt_number": gs.attempt_number,
        },
        "progress": {
            "level": next_level,
            "difficulty": suggestion["difficulty"],
            "coaching_blurb": suggestion.get("coaching_blurb"),
            "source": suggestion.get("source"),
            "passed": passed,
            "played_level": cur_level,
            "next_level": next_level,
        },
    }), 201
