"""Timed multiplayer game races: mixed puzzles, quizzes, and questions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm.attributes import flag_modified

from app import app, db
from app.models import Game, GameBankItem, GameRace, GameRaceItem, GameRacePlayer, GameUser


VALID_AGE_RANGES = [
    "Infants",
    "9-10",
    "11-12",
    "13-14",
    "15-16",
    "17-19",
    "9-19",
    "Youths & older",
]
ITEM_TYPES = ("puzzle", "quiz", "question")
RECENT_FINISHED_HOURS = 2


def _catalog_ages_for_race(age_range):
    """Games/bank items visible when building a race for this age."""
    ages = [age_range]
    if age_range in ("9-10", "11-12", "13-14", "15-16", "17-19"):
        ages.append("9-19")
    return ages


def _snapshot_bank_item(bank_item, points=None):
    """Turn a GameBankItem into a GameRaceItem row (immutable snapshot)."""
    kind = (bank_item.item_kind or "quiz").strip()
    pts = int(points if points is not None else (bank_item.points_default or 5))
    if pts < 1 or pts > 100:
        pts = 5
    payload = dict(bank_item.payload_json or {})
    prompt = (bank_item.prompt or "").strip()

    if kind == "puzzle":
        if not bank_item.game_id:
            raise ValueError("Bank puzzle is missing its source game")
        game = Game.query.get(bank_item.game_id)
        if not game:
            raise ValueError("Bank puzzle game not found")
        return {
            "item_type": "puzzle",
            "points": pts,
            "game_id": bank_item.game_id,
            "prompt": prompt or None,
            "payload_json": {
                "title_snapshot": game.title,
                "bank_item_id": bank_item.id,
                "bank_item_slug": bank_item.slug,
            },
        }

    if kind == "question":
        qkind = (payload.get("kind") or "short").strip()
        if qkind not in ("short", "true_false"):
            qkind = "short"
        accepted = payload.get("accepted_answers") or []
        if isinstance(accepted, str):
            accepted = [part.strip() for part in accepted.split(",") if part.strip()]
        accepted = [str(a).strip() for a in accepted if str(a).strip()]
        if not prompt:
            raise ValueError("Bank question needs a prompt")
        if qkind == "true_false" and not accepted:
            accepted = ["true"]
        if not accepted:
            raise ValueError("Bank question needs accepted answers")
        return {
            "item_type": "question",
            "points": pts,
            "game_id": bank_item.game_id,
            "prompt": prompt,
            "payload_json": {
                "kind": qkind,
                "accepted_answers": accepted,
                "bank_item_id": bank_item.id,
                "title_snapshot": bank_item.title,
            },
        }

    # Default: quiz
    options = payload.get("options") or []
    options = [str(opt).strip() for opt in options if str(opt).strip()]
    if not prompt:
        raise ValueError("Bank quiz needs a question")
    if len(options) < 2:
        raise ValueError("Bank quiz needs at least 2 options")
    try:
        correct_index = int(payload.get("correct_index"))
    except (TypeError, ValueError):
        raise ValueError("Bank quiz needs a correct option")
    if correct_index < 0 or correct_index >= len(options):
        raise ValueError("Bank quiz correct option is out of range")
    return {
        "item_type": "quiz",
        "points": pts,
        "game_id": bank_item.game_id,
        "prompt": prompt,
        "payload_json": {
            "options": options,
            "correct_index": correct_index,
            "bank_item_id": bank_item.id,
            "title_snapshot": bank_item.title,
        },
    }


def _staff_ok():
    return (
        current_user.is_authenticated
        and (
            current_user.userRole == "Admin"
            or current_user.has_privilege("Akello Events")
            or current_user.has_privilege("Content Development")
        )
    )


def _parse_iso_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _matching_age_ranges(age):
    if age is None:
        return []
    if age < 9:
        return ["Infants"]
    if 9 <= age <= 10:
        return ["9-10", "9-19"]
    if 11 <= age <= 12:
        return ["11-12", "9-19"]
    if 13 <= age <= 14:
        return ["13-14", "9-19"]
    if 15 <= age <= 16:
        return ["15-16", "9-19"]
    if 17 <= age <= 19:
        return ["17-19", "9-19"]
    return ["Youths & older"]


def _game_user_from_request(data=None):
    data = data or {}
    raw = data.get("user_id") or request.args.get("user_id") or request.args.get("game_user_id")
    if raw is None and request.is_json:
        raw = (request.get_json(silent=True) or {}).get("user_id")
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return None
    return GameUser.query.get(user_id)


def _normalize_answer(value):
    return " ".join(str(value or "").strip().lower().split())


def _item_payload(item, include_answers=False):
    payload = dict(item.payload_json or {})
    if not include_answers:
        payload.pop("correct_index", None)
        payload.pop("accepted_answers", None)
    return {
        "id": item.id,
        "sort_order": item.sort_order,
        "item_type": item.item_type,
        "points": item.points,
        "prompt": item.prompt,
        "payload": payload,
        "game_id": item.game_id,
        "game_title": item.game.title if item.game else (payload.get("title_snapshot") or None),
        "game_max_score": item.game.max_score if item.game else None,
    }


def _leaderboard(race, hide_scores=False):
    players = sorted(
        race.players,
        key=lambda p: (
            -(p.score or 0) if not hide_scores else -_draft_progress(race, p),
            p.submitted_at or datetime.max,
            p.joined_at or datetime.max,
        ),
    )
    rows = []
    for index, player in enumerate(players, 1):
        player.place = index
        user = player.game_user
        progress = _draft_progress(race, player)
        total_items = len(race.items)
        row_score = player.score or 0
        if hide_scores and not player.finished:
            row_score = progress
        rows.append({
            "user_id": player.game_user_id,
            "firstname": user.firstname if user else "",
            "surname": user.surname if user else "",
            "username": user.username if user else "",
            "score": row_score,
            "max_score": player.max_score,
            "percentage": player.percentage,
            "place": index,
            "finished": bool(player.finished),
            "progress": progress,
            "total_items": total_items,
            "show_progress": hide_scores and not player.finished,
            "joined_at": player.joined_at.isoformat() if player.joined_at else None,
            "submitted_at": player.submitted_at.isoformat() if player.submitted_at else None,
        })
    return rows


def _draft_progress(race, player):
    answers = player.answers_json or {}
    count = 0
    for item in race.items:
        entry = answers.get(str(item.id))
        if entry and (entry.get("draft") or entry.get("score") is not None):
            count += 1
    return count


def _grade_all_drafts(race, player):
    """Grade saved drafts and skipped items when a player finishes."""
    now = datetime.utcnow()
    answers = dict(player.answers_json or {})
    for item in race.items:
        key = str(item.id)
        entry = answers.get(key)
        if entry and entry.get("draft"):
            grade_payload = {
                "selected_index": entry.get("selected_index"),
                "answer": entry.get("answer"),
                "skipped": entry.get("skipped"),
                "score": entry.get("score"),
                "max_score": entry.get("max_score"),
            }
            if entry.get("skipped"):
                earned, maximum = 0, item.points
            else:
                earned, maximum = _grade_item(item, grade_payload)
            answers[key] = {
                "score": earned,
                "max": maximum,
                "answered_at": entry.get("saved_at") or now.isoformat(),
                "skipped": bool(entry.get("skipped")),
                "draft": False,
                "selected_index": entry.get("selected_index"),
                "answer": entry.get("answer"),
                "correct": earned == maximum,
            }
        elif key not in answers:
            answers[key] = {
                "score": 0,
                "max": item.points,
                "answered_at": now.isoformat(),
                "skipped": True,
                "draft": False,
            }
    player.answers_json = answers
    flag_modified(player, "answers_json")
    _recompute_player_score(race, player)


def _mix_summary(race):
    counts = race.mix_counts()
    return {
        "puzzle": counts["puzzle"],
        "quiz": counts["quiz"],
        "question": counts["question"],
        "total_items": len(race.items),
        "total_points": race.total_points(),
    }


def _serialize_race(race, include_items=False, include_answers=False, player=None):
    now = datetime.utcnow()
    data = {
        "id": race.id,
        "title": race.title,
        "age_range": race.age_range,
        "starts_at": race.starts_at.isoformat() if race.starts_at else None,
        "ends_at": race.ends_at.isoformat() if race.ends_at else None,
        "duration_minutes": race.duration_minutes,
        "status": race.status(now),
        "is_cancelled": bool(race.is_cancelled),
        "remaining_seconds": race.remaining_seconds(now),
        "seconds_until_start": race.seconds_until_start(now),
        "player_count": len(race.players),
        "mix": _mix_summary(race),
        "created_at": race.created_at.isoformat() if race.created_at else None,
    }
    if include_items:
        status = race.status(now)
        hide_scores = status == "live"
        data["items"] = [_item_payload(item, include_answers=include_answers) for item in race.items]
        data["leaderboard"] = _leaderboard(race, hide_scores=hide_scores)
    if player is not None:
        answers = player.answers_json or {}
        draft_ids = []
        finalized_ids = []
        for key, entry in answers.items():
            if not str(key).isdigit():
                continue
            if entry.get("draft"):
                draft_ids.append(int(key))
            elif entry.get("score") is not None:
                finalized_ids.append(int(key))
        data["me"] = {
            "user_id": player.game_user_id,
            "score": player.score or 0,
            "max_score": player.max_score or race.total_points(),
            "finished": bool(player.finished),
            "place": player.place,
            "draft_item_ids": draft_ids,
            "answered_item_ids": finalized_ids,
            "progress": _draft_progress(race, player),
            "answers": answers if include_answers else {
                k: {kk: vv for kk, vv in v.items() if kk not in ("correct",)}
                for k, v in answers.items()
            },
        }
    return data


def _recompute_player_score(race, player):
    answers = player.answers_json or {}
    total = 0
    for item in race.items:
        entry = answers.get(str(item.id))
        if entry and not entry.get("draft") and entry.get("score") is not None:
            total += int(entry.get("score") or 0)
    player.score = total
    player.max_score = race.total_points()
    player.percentage = (total / player.max_score * 100.0) if player.max_score else 0.0


def _finish_player(race, player, now=None):
    now = now or datetime.utcnow()
    _grade_all_drafts(race, player)
    player.finished = True
    player.submitted_at = player.submitted_at or now


def _emit_leaderboard(race):
    try:
        from app.socketio_handlers import emit_race_leaderboard
        hide_scores = race.status() == "live"
        emit_race_leaderboard(race.id, {
            "leaderboard": _leaderboard(race, hide_scores=hide_scores),
            "remaining_seconds": race.remaining_seconds(),
            "status": race.status(),
            "player_count": len(race.players),
        })
    except Exception:
        app.logger.exception("Failed to emit race leaderboard")


def _validate_items(raw_items):
    if not raw_items or not isinstance(raw_items, list):
        raise ValueError("Add at least one puzzle, quiz, or question")
    cleaned = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(f"Item {index + 1} is invalid")

        bank_item_id = raw.get("bank_item_id")
        if bank_item_id is not None and str(bank_item_id).strip() != "":
            try:
                bank_item = GameBankItem.query.get(int(bank_item_id))
            except (TypeError, ValueError):
                raise ValueError(f"Item {index + 1}: invalid bank item")
            if not bank_item or not bank_item.is_active:
                raise ValueError(f"Item {index + 1}: bank item not found")
            try:
                snap = _snapshot_bank_item(bank_item, points=raw.get("points"))
            except ValueError as exc:
                raise ValueError(f"Item {index + 1}: {exc}") from exc
            snap["sort_order"] = index
            cleaned.append(snap)
            continue

        item_type = (raw.get("item_type") or "").strip()
        if item_type not in ITEM_TYPES:
            raise ValueError(f"Item {index + 1}: type must be puzzle, quiz, or question")
        try:
            points = int(raw.get("points") or 1)
        except (TypeError, ValueError):
            raise ValueError(f"Item {index + 1}: points must be a number")
        if points < 1 or points > 100:
            raise ValueError(f"Item {index + 1}: points must be between 1 and 100")

        payload = dict(raw.get("payload") or raw.get("payload_json") or {})
        prompt = (raw.get("prompt") or "").strip()
        game_id = None

        if item_type == "puzzle":
            try:
                game_id = int(raw.get("game_id") or payload.get("game_id"))
            except (TypeError, ValueError):
                raise ValueError(f"Item {index + 1}: choose a puzzle game")
            game = Game.query.get(game_id)
            if not game:
                raise ValueError(f"Item {index + 1}: puzzle game not found")
            payload = {"title_snapshot": game.title}

        elif item_type == "quiz":
            options = raw.get("options") or payload.get("options") or []
            options = [str(opt).strip() for opt in options if str(opt).strip()]
            if not prompt:
                raise ValueError(f"Item {index + 1}: quiz needs a question")
            if len(options) < 2:
                raise ValueError(f"Item {index + 1}: quiz needs at least 2 options")
            try:
                correct_index = int(raw.get("correct_index") if raw.get("correct_index") is not None else payload.get("correct_index"))
            except (TypeError, ValueError):
                raise ValueError(f"Item {index + 1}: mark the correct quiz option")
            if correct_index < 0 or correct_index >= len(options):
                raise ValueError(f"Item {index + 1}: correct option is out of range")
            payload = {"options": options, "correct_index": correct_index}

        else:
            kind = (raw.get("kind") or payload.get("kind") or "short").strip()
            if kind not in ("short", "true_false"):
                kind = "short"
            if not prompt:
                raise ValueError(f"Item {index + 1}: question needs a prompt")
            accepted = raw.get("accepted_answers") or payload.get("accepted_answers") or []
            if isinstance(accepted, str):
                accepted = [part.strip() for part in accepted.split(",") if part.strip()]
            accepted = [str(ans).strip() for ans in accepted if str(ans).strip()]
            if kind == "true_false":
                if not accepted:
                    tf = raw.get("answer") or payload.get("answer") or "true"
                    accepted = [str(tf).strip().lower()]
                accepted = ["true" if _normalize_answer(a) in ("true", "t", "yes", "1") else "false" for a in accepted]
            elif not accepted:
                raise ValueError(f"Item {index + 1}: add at least one accepted answer")
            payload = {"kind": kind, "accepted_answers": accepted}

        cleaned.append({
            "sort_order": index,
            "item_type": item_type,
            "points": points,
            "game_id": game_id,
            "prompt": prompt or None,
            "payload_json": payload,
        })
    return cleaned


def _replace_items(race, cleaned):
    for item in list(race.items):
        db.session.delete(item)
    db.session.flush()
    for row in cleaned:
        db.session.add(GameRaceItem(race=race, **row))


def _grade_item(item, data):
    if item.item_type == "quiz":
        payload = item.payload_json or {}
        try:
            selected = int(data.get("selected_index"))
        except (TypeError, ValueError):
            selected = None
        correct = payload.get("correct_index")
        earned = item.points if selected is not None and selected == correct else 0
        return earned, item.points

    if item.item_type == "question":
        payload = item.payload_json or {}
        kind = payload.get("kind") or "short"
        given = _normalize_answer(data.get("answer"))
        accepted = [_normalize_answer(a) for a in (payload.get("accepted_answers") or [])]
        if kind == "true_false":
            if given in ("t", "yes", "1"):
                given = "true"
            elif given in ("f", "no", "0"):
                given = "false"
        earned = item.points if given and given in accepted else 0
        return earned, item.points

    raw_score = 0
    try:
        raw_score = int(data.get("score") or 0)
    except (TypeError, ValueError):
        raw_score = 0
    raw_max = 0
    try:
        raw_max = int(data.get("max_score") or (item.game.max_score if item.game else 0) or 0)
    except (TypeError, ValueError):
        raw_max = 0
    if raw_max > 0:
        earned = int(round(item.points * (max(0, raw_score) / float(raw_max))))
    else:
        earned = max(0, min(item.points, raw_score))
    return max(0, min(item.points, earned)), item.points


@app.route("/play-race/<int:race_id>")
def play_race(race_id):
    race = GameRace.query.get_or_404(race_id)
    return render_template("play_race.html", title=race.title, race_id=race.id)


@app.route("/api/game-races", methods=["GET"])
@login_required
def list_game_races_admin():
    if not _staff_ok():
        return jsonify({"error": "Unauthorized"}), 403
    races = GameRace.query.order_by(GameRace.starts_at.desc()).all()
    return jsonify({"races": [_serialize_race(race) for race in races]}), 200


@app.route("/api/game-races", methods=["POST"])
@login_required
def create_game_race():
    if not _staff_ok():
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    age_range = (data.get("age_range") or "").strip()
    duration_minutes = data.get("duration_minutes")
    starts_at = _parse_iso_datetime(data.get("starts_at"))
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if age_range not in VALID_AGE_RANGES:
        return jsonify({"error": f"Age range must be one of: {', '.join(VALID_AGE_RANGES)}"}), 400
    try:
        duration_minutes = int(duration_minutes)
    except (TypeError, ValueError):
        return jsonify({"error": "Duration must be a number of minutes"}), 400
    if duration_minutes < 1 or duration_minutes > 180:
        return jsonify({"error": "Duration must be between 1 and 180 minutes"}), 400
    if not starts_at:
        return jsonify({"error": "Start time is required"}), 400
    try:
        cleaned = _validate_items(data.get("items"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    race = GameRace(
        title=title,
        age_range=age_range,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        ends_at=starts_at + timedelta(minutes=duration_minutes),
        created_by=current_user.id,
        is_cancelled=False,
    )
    db.session.add(race)
    db.session.flush()
    _replace_items(race, cleaned)
    db.session.commit()
    return jsonify({"race": _serialize_race(race, include_items=True, include_answers=True)}), 201


@app.route("/api/game-races/<int:race_id>", methods=["PUT"])
@login_required
def update_game_race(race_id):
    if not _staff_ok():
        return jsonify({"error": "Unauthorized"}), 403
    race = GameRace.query.get_or_404(race_id)
    data = request.get_json() or {}
    if data.get("is_cancelled") is True or data.get("cancel") is True:
        race.is_cancelled = True
        db.session.commit()
        return jsonify({"race": _serialize_race(race, include_items=True, include_answers=True)}), 200

    if race.status() == "finished":
        return jsonify({"error": "Finished races cannot be edited"}), 400

    if race.status() == "live" and data.get("items"):
        return jsonify({"error": "Cannot change the playlist after a race has started"}), 400

    if data.get("title"):
        race.title = data["title"].strip()
    if data.get("age_range"):
        age_range = data["age_range"].strip()
        if age_range not in VALID_AGE_RANGES:
            return jsonify({"error": f"Age range must be one of: {', '.join(VALID_AGE_RANGES)}"}), 400
        race.age_range = age_range
    if data.get("duration_minutes") is not None:
        try:
            duration_minutes = int(data.get("duration_minutes"))
        except (TypeError, ValueError):
            return jsonify({"error": "Duration must be a number of minutes"}), 400
        if duration_minutes < 1 or duration_minutes > 180:
            return jsonify({"error": "Duration must be between 1 and 180 minutes"}), 400
        race.duration_minutes = duration_minutes
    if data.get("starts_at"):
        starts_at = _parse_iso_datetime(data.get("starts_at"))
        if not starts_at:
            return jsonify({"error": "Start time is invalid"}), 400
        race.starts_at = starts_at
    race.ends_at = race.starts_at + timedelta(minutes=race.duration_minutes)

    if "items" in data:
        try:
            cleaned = _validate_items(data.get("items"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        _replace_items(race, cleaned)

    db.session.commit()
    return jsonify({"race": _serialize_race(race, include_items=True, include_answers=True)}), 200


@app.route("/api/game-races/<int:race_id>/results", methods=["GET"])
@login_required
def game_race_results(race_id):
    if not _staff_ok():
        return jsonify({"error": "Unauthorized"}), 403
    race = GameRace.query.get_or_404(race_id)
    board = _leaderboard(race)
    db.session.commit()
    return jsonify({
        "race": _serialize_race(race, include_items=True, include_answers=True),
        "leaderboard": board,
    }), 200


@app.route("/api/game-races/available", methods=["GET"])
def list_available_game_races():
    game_user = _game_user_from_request()
    if not game_user:
        return jsonify({"error": "user_id is required"}), 400
    ranges = _matching_age_ranges(game_user.age)
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(hours=RECENT_FINISHED_HOURS)
    races = (
        GameRace.query.filter(
            GameRace.is_cancelled.is_(False),
            GameRace.age_range.in_(ranges or ["__none__"]),
            GameRace.ends_at >= recent_cutoff,
        )
        .order_by(GameRace.starts_at.asc())
        .all()
    )
    payload = []
    for race in races:
        row = _serialize_race(race)
        player = next((p for p in race.players if p.game_user_id == game_user.id), None)
        row["joined"] = player is not None
        row["finished"] = bool(player.finished) if player else False
        payload.append(row)
    return jsonify({"races": payload}), 200


@app.route("/api/game-races/<int:race_id>/join", methods=["POST"])
def join_game_race(race_id):
    data = request.get_json() or {}
    game_user = _game_user_from_request(data)
    if not game_user:
        return jsonify({"error": "user_id is required"}), 400
    race = GameRace.query.get_or_404(race_id)
    status = race.status()
    if race.is_cancelled:
        return jsonify({"error": "This race was cancelled"}), 400
    if status == "finished":
        return jsonify({"error": "This race has already ended"}), 400
    ranges = _matching_age_ranges(game_user.age)
    if race.age_range not in ranges:
        return jsonify({"error": "This race is not for your age group"}), 400

    player = GameRacePlayer.query.filter_by(race_id=race.id, game_user_id=game_user.id).first()
    if not player:
        player = GameRacePlayer(
            race_id=race.id,
            game_user_id=game_user.id,
            score=0,
            max_score=race.total_points(),
            percentage=0,
            finished=False,
            answers_json={},
        )
        db.session.add(player)
        db.session.flush()
        _leaderboard(race)
        db.session.commit()
        _emit_leaderboard(race)
    else:
        db.session.commit()

    return jsonify({"race": _serialize_race(race, include_items=True, player=player)}), 200


@app.route("/api/game-races/<int:race_id>", methods=["GET"])
def get_game_race(race_id):
    race = GameRace.query.get_or_404(race_id)
    game_user = _game_user_from_request()
    player = None
    if game_user:
        player = GameRacePlayer.query.filter_by(race_id=race.id, game_user_id=game_user.id).first()
    include_answers = race.status() == "finished" or _staff_ok()
    payload = _serialize_race(race, include_items=True, include_answers=include_answers, player=player)
    return jsonify({"race": payload}), 200


@app.route("/api/game-races/<int:race_id>/items/<int:item_id>/draft", methods=["POST"])
def draft_game_race_item(race_id, item_id):
    """Save a draft answer without grading (quiz/question only)."""
    data = request.get_json() or {}
    game_user = _game_user_from_request(data)
    if not game_user:
        return jsonify({"error": "user_id is required"}), 400
    race = GameRace.query.get_or_404(race_id)
    if race.status() != "live":
        return jsonify({"error": "Drafts are only accepted while the race is live"}), 400
    player = GameRacePlayer.query.filter_by(race_id=race.id, game_user_id=game_user.id).first()
    if not player:
        return jsonify({"error": "Join the race first"}), 400
    if player.finished:
        return jsonify({"error": "You have already finished this race"}), 400
    item = GameRaceItem.query.filter_by(id=item_id, race_id=race.id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    if item.item_type == "puzzle":
        return jsonify({"error": "Use puzzle submit for game scores"}), 400

    answers = dict(player.answers_json or {})
    answers[str(item.id)] = {
        "draft": True,
        "score": None,
        "max": item.points,
        "selected_index": data.get("selected_index"),
        "answer": data.get("answer"),
        "skipped": bool(data.get("skipped")),
        "saved_at": datetime.utcnow().isoformat(),
    }
    player.answers_json = answers
    flag_modified(player, "answers_json")
    hide_scores = race.status() == "live"
    _leaderboard(race, hide_scores=hide_scores)
    db.session.commit()
    _emit_leaderboard(race)
    return jsonify({
        "saved": True,
        "progress": _draft_progress(race, player),
        "race": _serialize_race(race, include_items=True, player=player),
    }), 200


@app.route("/api/game-races/<int:race_id>/items/<int:item_id>/submit", methods=["POST"])
def submit_game_race_item(race_id, item_id):
    data = request.get_json() or {}
    game_user = _game_user_from_request(data)
    if not game_user:
        return jsonify({"error": "user_id is required"}), 400
    race = GameRace.query.get_or_404(race_id)
    if race.status() != "live":
        return jsonify({"error": "Answers are only accepted while the race is live"}), 400
    player = GameRacePlayer.query.filter_by(race_id=race.id, game_user_id=game_user.id).first()
    if not player:
        return jsonify({"error": "Join the race first"}), 400
    if player.finished:
        return jsonify({"error": "You have already finished this race"}), 400
    item = GameRaceItem.query.filter_by(id=item_id, race_id=race.id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # Quiz/question: store draft only; grading happens on finish
    if item.item_type in ("quiz", "question"):
        answers = dict(player.answers_json or {})
        answers[str(item.id)] = {
            "draft": True,
            "score": None,
            "max": item.points,
            "selected_index": data.get("selected_index"),
            "answer": data.get("answer"),
            "skipped": bool(data.get("skipped")),
            "saved_at": datetime.utcnow().isoformat(),
        }
        player.answers_json = answers
        flag_modified(player, "answers_json")
        hide_scores = race.status() == "live"
        _leaderboard(race, hide_scores=hide_scores)
        db.session.commit()
        _emit_leaderboard(race)
        return jsonify({
            "saved": True,
            "progress": _draft_progress(race, player),
            "race": _serialize_race(race, include_items=True, player=player),
        }), 200

    # Puzzle: accept final game score (graded immediately)
    earned, maximum = _grade_item(item, data)
    answers = dict(player.answers_json or {})
    answers[str(item.id)] = {
        "score": earned,
        "max": maximum,
        "answered_at": datetime.utcnow().isoformat(),
        "skipped": False,
        "draft": False,
        "correct": earned == maximum,
    }
    player.answers_json = answers
    flag_modified(player, "answers_json")
    _recompute_player_score(race, player)
    hide_scores = race.status() == "live"
    _leaderboard(race, hide_scores=hide_scores)
    db.session.commit()
    _emit_leaderboard(race)
    return jsonify({
        "earned": earned,
        "max": maximum,
        "correct": earned == maximum,
        "race": _serialize_race(race, include_items=True, player=player),
    }), 200


@app.route("/api/game-races/<int:race_id>/finish", methods=["POST"])
def finish_game_race(race_id):
    data = request.get_json() or {}
    game_user = _game_user_from_request(data)
    if not game_user:
        return jsonify({"error": "user_id is required"}), 400
    race = GameRace.query.get_or_404(race_id)
    player = GameRacePlayer.query.filter_by(race_id=race.id, game_user_id=game_user.id).first()
    if not player:
        return jsonify({"error": "Join the race first"}), 400
    _finish_player(race, player)
    _leaderboard(race)
    db.session.commit()
    _emit_leaderboard(race)
    return jsonify({"race": _serialize_race(race, include_items=True, include_answers=True, player=player)}), 200
