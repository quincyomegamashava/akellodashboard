"""Authenticate Smart Learning / Ruzivo students against tblstudents."""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime
from typing import Any

from app import db
from app.models import GameUser


class RuzivoAuthError(Exception):
    """Raised when Ruzivo credentials are invalid or the account cannot play."""

    def __init__(self, message: str, *, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def _md5_hex(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def parse_dob(value) -> date | None:
    """Normalize DOB from Ruzivo / form input to a date, or None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        if value.year < 1900:
            return None
        return value
    if isinstance(value, str):
        text = value.strip()[:10]
        if not text or text.startswith("0000"):
            return None
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
        if parsed.year < 1900:
            return None
        return parsed
    return None


def age_from_dob(dob) -> int | None:
    dob = parse_dob(dob)
    if not dob:
        return None
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 0 or age > 150:
        return None
    return age


def _age_from_grade(grade) -> int | None:
    """Rough Zimbabwe grade → age fallback when DOB is missing (temporary only)."""
    try:
        g = int(grade)
    except (TypeError, ValueError):
        return None
    grade_age = {
        0: 5, 1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 11, 7: 12,
        8: 13, 9: 14, 10: 15, 11: 16, 12: 17, 13: 18,
    }
    return grade_age.get(g)


def authenticate_student(username: str, password: str) -> dict[str, Any]:
    """
    Verify username + plaintext password against Ruzivo tblstudents (MD5).

    Returns a normalized student dict on success.
    Raises RuzivoAuthError on failure.
    """
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        raise RuzivoAuthError("Username and password are required")

    from app.routes import get_ruzivo_conn

    pwd_hash = _md5_hex(password)
    conn = None
    row = None
    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT s.student_id, s.username, s.name, s.surname, s.dob, s.grade,
                       s.gender, s.active, s.flag, s.email, i.mobile
                FROM tblstudents s
                INNER JOIN tblstudents_info i ON i.student_id = s.student_id
                WHERE s.username = %s AND s.password = %s AND s.flag != 'D'
                LIMIT 1
                """,
                (username, pwd_hash),
            )
            row = cursor.fetchone()
        finally:
            try:
                cursor.close()
            except Exception:
                pass
    except RuzivoAuthError:
        raise
    except Exception as exc:
        from flask import current_app
        try:
            current_app.logger.exception("Ruzivo student auth query failed: %s", exc)
        except Exception:
            pass
        raise RuzivoAuthError(
            "Unable to reach Smart Learning right now. Please try again later.",
            status_code=503,
        ) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not row:
        raise RuzivoAuthError("Invalid username or password")

    if not isinstance(row, dict):
        raise RuzivoAuthError(
            "Unable to reach Smart Learning right now. Please try again later.",
            status_code=503,
        )

    active = str(row.get("active") or "").strip()
    if active and active.lower() not in ("yes", "y", "1", "true"):
        raise RuzivoAuthError(
            "Your Smart Learning account is inactive. Contact support or reactivate on Smart Learning.",
            status_code=403,
        )

    return {
        "student_id": int(row["student_id"]),
        "username": (row.get("username") or username).strip(),
        "name": (row.get("name") or "").strip() or "Learner",
        "surname": (row.get("surname") or "").strip() or "Student",
        "dob": parse_dob(row.get("dob")),
        "grade": row.get("grade"),
        "gender": row.get("gender"),
        "mobile": (row.get("mobile") or "").strip() or None,
        "email": (row.get("email") or "").strip() or None,
        "active": active,
    }


def sync_game_user_from_ruzivo(student: dict[str, Any]) -> GameUser:
    """Create or update a local GameUser linked to the Ruzivo student."""
    student_id = int(student["student_id"])
    username = student["username"]

    game_user = GameUser.query.filter_by(ruzivo_student_id=student_id).first()
    if game_user is None:
        game_user = GameUser.query.filter_by(username=username).first()

    ruzivo_dob = parse_dob(student.get("dob"))
    # Prefer Ruzivo DOB when present; otherwise keep any DOB already saved locally
    effective_dob = ruzivo_dob
    if effective_dob is None and game_user is not None:
        effective_dob = parse_dob(getattr(game_user, "dob", None))

    age = age_from_dob(effective_dob)
    if age is None:
        age = _age_from_grade(student.get("grade"))
    if age is None and game_user is not None and game_user.age:
        age = game_user.age
    if age is None:
        age = 12  # temporary until learner supplies DOB

    phone = student.get("mobile")
    if phone and len(phone) > 20:
        phone = phone[:20]

    grade_val = None
    try:
        if student.get("grade") is not None and str(student.get("grade")).strip() != "":
            grade_val = int(student["grade"])
    except (TypeError, ValueError):
        grade_val = None

    now = datetime.utcnow()
    if game_user is None:
        game_user = GameUser(
            firstname=student["name"][:64],
            surname=student["surname"][:64],
            username=username[:64],
            age=age,
            phone_number=phone,
            ruzivo_student_id=student_id,
            grade=grade_val,
            dob=effective_dob,
            auth_source="ruzivo",
            last_ruzivo_sync_at=now,
            last_login=now,
        )
        game_user.password_hash = generate_unusable_password_hash()
        game_user.age_range = game_user.determine_age_range()
        db.session.add(game_user)
    else:
        game_user.firstname = student["name"][:64]
        game_user.surname = student["surname"][:64]
        game_user.username = username[:64]
        game_user.age = age
        game_user.phone_number = phone
        game_user.ruzivo_student_id = student_id
        game_user.grade = grade_val
        if effective_dob is not None:
            game_user.dob = effective_dob
        game_user.auth_source = "ruzivo"
        game_user.last_ruzivo_sync_at = now
        game_user.last_login = now
        game_user.age_range = game_user.determine_age_range()

    return game_user


def apply_local_dob(game_user: GameUser, dob_value) -> GameUser:
    """Persist learner-entered DOB and recompute age / age_range."""
    dob = parse_dob(dob_value)
    if not dob:
        raise ValueError("Enter a valid date of birth (YYYY-MM-DD)")
    if dob > date.today():
        raise ValueError("Date of birth cannot be in the future")
    age = age_from_dob(dob)
    if age is None:
        raise ValueError("Date of birth is out of range")
    game_user.dob = dob
    game_user.age = age
    game_user.age_range = game_user.determine_age_range()
    return game_user


def user_needs_dob(game_user: GameUser) -> bool:
    return parse_dob(getattr(game_user, "dob", None)) is None


def generate_unusable_password_hash() -> str:
    """Werkzeug-style hash that cannot match any real password."""
    from werkzeug.security import generate_password_hash

    return generate_password_hash(secrets.token_urlsafe(48))
