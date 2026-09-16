"""Province stats data fetching, cache keys, and MTD prewarm helpers."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional, Tuple

import pymysql.cursors

logger = logging.getLogger(__name__)

VALID_PROVINCES = (
    "Harare",
    "Bulawayo",
    "Manicaland",
    "Mashonaland Central",
    "Mashonaland East",
    "Mashonaland West",
    "Masvingo",
    "Matabeleland North",
    "Matabeleland South",
    "Midlands",
)

CACHE_TTL = 900  # 15 minutes
CHUNK = 1000


def is_valid_province(name: Optional[str]) -> bool:
    return bool(name) and name in VALID_PROVINCES


def normalize_date_str(value: Any) -> str:
    """Normalize a date or date-string to YYYY-MM-DD."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value or "").strip()
    if len(s) >= 10:
        return s[:10]
    return s


def cache_key(metric: str, province: str, start: Any, end: Any) -> str:
    return f"ps:{metric}:{province}:{normalize_date_str(start)}:{normalize_date_str(end)}"


def mtd_range(today: Optional[date] = None) -> Tuple[date, date]:
    today = today or datetime.today().date()
    return today.replace(day=1), today


def _get_cache():
    from app.routes import cache
    return cache


def _get_ruzivo_conn():
    from app.routes import get_ruzivo_conn
    return get_ruzivo_conn()


def _get_ruzivo_pool():
    from app.routes import get_ruzivo_pool
    return get_ruzivo_pool()


def _get_library_conn():
    from app.routes import get_direct_library_conn
    return get_direct_library_conn()


def _ba_user_index(province_name: str) -> dict:
    from app.models import User

    local_champions = User.query.filter(
        User.province == province_name,
        User.userRole == "Brand Ambassador",
    ).all()
    return {
        (
            (u.firstname or "").strip().lower(),
            (u.lastname or "").strip().lower(),
            (u.province or "").strip().lower(),
        ): u.username
        for u in local_champions
    }


def _lookup_username(user_index: dict, champ) -> Optional[str]:
    return user_index.get((
        (champ.firstname or "").strip().lower(),
        (champ.lastname or "").strip().lower(),
        (champ.province or "").strip().lower(),
    ))


def fetch_overview(province_name: str, start_date: date, end_date: date) -> dict:
    """
    Champion Overview metrics for a province.
    Returns {"ok": True, "data": [...]} or {"ok": False, "error": "..."}.
    """
    from app.models import ChampionSchool

    champions = ChampionSchool.query.filter_by(province=province_name).all()
    user_index = _ba_user_index(province_name)

    champ_asl = {}
    champ_lib = {}
    all_asl_ids, all_lib_ids = [], []

    for champ in champions:
        schools = champ.get_schools() or []
        asl_ids = [
            int(s.get("asl_school_id"))
            for s in schools
            if str(s.get("asl_school_id") or "").strip().isdigit()
        ]
        lib_ids = [
            int(s.get("library_school_id"))
            for s in schools
            if str(s.get("library_school_id") or "").strip().isdigit()
        ]
        if asl_ids:
            champ_asl[champ.id] = asl_ids
            all_asl_ids.extend(asl_ids)
        if lib_ids:
            champ_lib[champ.id] = lib_ids
            all_lib_ids.extend(lib_ids)

    all_asl_ids = sorted(set(all_asl_ids))
    all_lib_ids = sorted(set(all_lib_ids))

    if not all_asl_ids and not all_lib_ids:
        return {"ok": True, "data": []}

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    errors = []

    asl_counts_by_school = {}
    if all_asl_ids:
        conn = None
        cursor = None
        try:
            pool = _get_ruzivo_pool()
            if pool is None:
                errors.append("Ruzivo pool not available")
            else:
                conn = pool.connection()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                for i in range(0, len(all_asl_ids), CHUNK):
                    chunk = all_asl_ids[i:i + CHUNK]
                    placeholders = ",".join(["%s"] * len(chunk))
                    query = f"""
                        SELECT school_id, COUNT(DISTINCT student_id) AS student_count
                        FROM vwstudent
                        WHERE school_id IN ({placeholders})
                          AND last_login BETWEEN %s AND %s
                        GROUP BY school_id
                    """
                    cursor.execute(query, chunk + [start_dt, end_dt])
                    for row in cursor.fetchall() or []:
                        sid = int(row["school_id"])
                        asl_counts_by_school[sid] = int(row["student_count"] or 0)
        except Exception as e:
            logger.error("ASL bulk query error: %s", e)
            errors.append(f"ASL query failed: {e}")
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    lib_counts_by_inst = {}
    if all_lib_ids:
        conn = None
        cursor = None
        try:
            conn = _get_library_conn()
            if conn:
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                for i in range(0, len(all_lib_ids), CHUNK):
                    chunk = all_lib_ids[i:i + CHUNK]
                    placeholders = ",".join(["%s"] * len(chunk))
                    query = f"""
                        SELECT iu.institution_id AS inst_id, COUNT(DISTINCT la.user_id) AS active_users
                        FROM logins la
                        JOIN institution_user iu ON la.user_id = iu.user_id
                        WHERE iu.institution_id IN ({placeholders})
                          AND la.created_at BETWEEN %s AND %s
                        GROUP BY iu.institution_id
                    """
                    cursor.execute(query, chunk + [start_dt, end_dt])
                    for row in cursor.fetchall() or []:
                        iid = int(row["inst_id"])
                        lib_counts_by_inst[iid] = int(row["active_users"] or 0)
        except Exception as e:
            logger.error("Library bulk query error: %s", e)
            errors.append(f"Library query failed: {e}")
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    if errors and not asl_counts_by_school and not lib_counts_by_inst and (all_asl_ids or all_lib_ids):
        return {"ok": False, "error": "; ".join(errors)}

    results = []
    for champ in champions:
        asl_ids = champ_asl.get(champ.id, [])
        lib_ids = champ_lib.get(champ.id, [])
        if not asl_ids and not lib_ids:
            continue
        asl_student_count = sum(asl_counts_by_school.get(int(sid), 0) for sid in asl_ids)
        library_student_count = sum(lib_counts_by_inst.get(int(iid), 0) for iid in lib_ids)
        results.append({
            "champion": f"{champ.firstname} {champ.lastname}",
            "username": _lookup_username(user_index, champ),
            "school_count": len(asl_ids),
            "asl_student_count": asl_student_count,
            "library_student_count": library_student_count,
            "overall_student_count": asl_student_count + library_student_count,
        })

    payload = {"ok": True, "data": results}
    if errors:
        payload["warnings"] = errors
    return payload


def fetch_ask_akello(province_name: str, start_date: datetime, end_date: datetime) -> dict:
    """
    Ask Akello chat counts per champion.
    Returns {"ok": True, "data": [...]} or {"ok": False, "error": "..."}.
    """
    from app.models import ChampionSchool

    champions = ChampionSchool.query.filter_by(province=province_name).all()
    user_index = _ba_user_index(province_name)

    champ_to_asl = {}
    all_asl_ids = []
    for champ in champions:
        schools = champ.get_schools() or []
        ids = []
        for s in schools:
            raw = str(s.get("asl_school_id") or "").strip()
            if raw.isdigit():
                sid = int(raw)
                ids.append(sid)
                all_asl_ids.append(sid)
        champ_to_asl[champ.id] = ids

    counts_by_school = {}
    if all_asl_ids:
        all_asl_ids = sorted(set(all_asl_ids))
        conn = None
        cursor = None
        try:
            conn = _get_ruzivo_conn()
            if conn is None:
                return {"ok": False, "error": "Database connection not available"}
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            for i in range(0, len(all_asl_ids), CHUNK):
                chunk = all_asl_ids[i:i + CHUNK]
                placeholders = ",".join(["%s"] * len(chunk))
                chatlog_query = f"""
                    SELECT
                        sc.school_id,
                        COUNT(DISTINCT tl.student_id) AS chatlog_count
                    FROM tblask_akello_chat_logs tl
                    LEFT JOIN tblstudents ts ON ts.student_id = tl.student_id
                    LEFT JOIN tblschools sc ON sc.school_id = ts.school_id
                    WHERE sc.school_id IN ({placeholders})
                      AND tl.created_at >= %s AND tl.created_at < %s
                    GROUP BY sc.school_id
                """
                cursor.execute(chatlog_query, (*chunk, start_date, end_date))
                for row in cursor.fetchall() or []:
                    sid = int(row["school_id"])
                    counts_by_school[sid] = counts_by_school.get(sid, 0) + int(row["chatlog_count"] or 0)
        except Exception as e:
            logger.error("Ask Akello query error: %s", e)
            return {"ok": False, "error": str(e)}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    results = []
    for champ in champions:
        asl_ids = champ_to_asl.get(champ.id, [])
        # Include champions even with no ASL IDs (chatlog_count 0)
        chatlog_count = sum(counts_by_school.get(sid, 0) for sid in asl_ids)
        results.append({
            "champion": f"{champ.firstname} {champ.lastname}",
            "username": _lookup_username(user_index, champ),
            "school_count": len(asl_ids),
            "chatlog_count": chatlog_count,
        })

    return {"ok": True, "data": results}


def fetch_asl_active_logins(province: str, start_date: date, end_date: date) -> dict:
    """Smartlearning active learners by school for a province."""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    conn = None
    cursor = None
    try:
        conn = _get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT
                sch.school_id,
                sch.school_name,
                sch.school_province,
                COUNT(DISTINCT sl.student_id) AS active_learners
            FROM tblstudents_login sl
            INNER JOIN tblstudents st ON sl.student_id = st.student_id
            INNER JOIN tblschools sch ON st.school_id = sch.school_id
            WHERE sl.login_date >= %s AND sl.login_date < %s
              AND sch.school_province = %s
            GROUP BY sch.school_id, sch.school_name, sch.school_province
            ORDER BY active_learners DESC
        """
        cursor.execute(query, (start_dt, end_dt_exclusive, province))
        results = cursor.fetchall() or []
        province_total = sum(int(row["active_learners"] or 0) for row in results)
        return {
            "ok": True,
            "data": {
                "province": province,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "province_total": province_total,
                "schools": results,
            },
        }
    except Exception as e:
        logger.error("ASL active logins error: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def fetch_library_institution_logins(province: str, start_date: date, end_date: date) -> dict:
    """Library distinct login users per institution in a province."""
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    conn = None
    cursor = None
    try:
        conn = _get_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT
                i.province,
                i.name AS institution_name,
                COUNT(DISTINCT l.user_id) AS user_count
            FROM users u
            INNER JOIN logins l ON l.user_id = u.id
            INNER JOIN institution_user iu ON iu.user_id = u.id
            INNER JOIN institutions i ON i.id = iu.institution_id
            WHERE i.province = %s
              AND l.created_at >= %s AND l.created_at < %s
            GROUP BY i.id, i.name, i.province
            ORDER BY user_count DESC
        """
        cursor.execute(query, (province, start_dt, end_exclusive))
        results = cursor.fetchall() or []
        return {
            "ok": True,
            "data": {
                "province": province,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "institutions": results,
            },
        }
    except Exception as e:
        logger.error("Library institution logins error: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _cache_get(key: str):
    try:
        return _get_cache().get(key)
    except Exception as e:
        logger.warning("cache get failed for %s: %s", key, e)
        return None


def _cache_set(key: str, value: Any, timeout: int = CACHE_TTL):
    try:
        _get_cache().set(key, value, timeout=timeout)
    except Exception as e:
        logger.warning("cache set failed for %s: %s", key, e)


def get_or_fetch_overview(province: str, start_date: date, end_date: date) -> dict:
    key = cache_key("overview", province, start_date, end_date)
    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    result = fetch_overview(province, start_date, end_date)
    if result.get("ok") and result.get("data"):
        _cache_set(key, result["data"])
    return result


def get_or_fetch_ask_akello(province: str, start_date: date, end_date: date) -> dict:
    """start_date/end_date are inclusive calendar dates (same as Overview)."""
    key = cache_key("ask", province, start_date, end_date)
    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    result = fetch_ask_akello(province, start_dt, end_dt_exclusive)
    if result.get("ok") and result.get("data"):
        _cache_set(key, result["data"])
    return result


def get_or_fetch_asl_active(province: str, start_date: date, end_date: date) -> dict:
    key = cache_key("asl", province, start_date, end_date)
    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    result = fetch_asl_active_logins(province, start_date, end_date)
    if result.get("ok") and result.get("data") and result["data"].get("schools"):
        _cache_set(key, result["data"])
    return result


def get_or_fetch_library(province: str, start_date: date, end_date: date) -> dict:
    key = cache_key("lib", province, start_date, end_date)
    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "data": cached, "cached": True}
    result = fetch_library_institution_logins(province, start_date, end_date)
    if result.get("ok") and result.get("data") and result["data"].get("institutions"):
        _cache_set(key, result["data"])
    return result


def prewarm_mtd_province(province: str, today: Optional[date] = None) -> dict:
    """Compute and cache MTD payloads for one province. Returns status per metric."""
    start, end = mtd_range(today)

    status = {}
    try:
        r = fetch_overview(province, start, end)
        if r.get("ok"):
            if r.get("data"):
                _cache_set(cache_key("overview", province, start, end), r["data"])
            status["overview"] = "ok"
        else:
            status["overview"] = r.get("error", "failed")
    except Exception as e:
        status["overview"] = str(e)

    try:
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt_exclusive = datetime.combine(end + timedelta(days=1), datetime.min.time())
        r = fetch_ask_akello(province, start_dt, end_dt_exclusive)
        if r.get("ok"):
            if r.get("data"):
                _cache_set(cache_key("ask", province, start, end), r["data"])
            status["ask"] = "ok"
        else:
            status["ask"] = r.get("error", "failed")
    except Exception as e:
        status["ask"] = str(e)

    try:
        r = fetch_asl_active_logins(province, start, end)
        if r.get("ok"):
            if r.get("data", {}).get("schools"):
                _cache_set(cache_key("asl", province, start, end), r["data"])
            status["asl"] = "ok"
        else:
            status["asl"] = r.get("error", "failed")
    except Exception as e:
        status["asl"] = str(e)

    try:
        r = fetch_library_institution_logins(province, start, end)
        if r.get("ok"):
            if r.get("data", {}).get("institutions"):
                _cache_set(cache_key("lib", province, start, end), r["data"])
            status["lib"] = "ok"
        else:
            status["lib"] = r.get("error", "failed")
    except Exception as e:
        status["lib"] = str(e)

    return status


def run_province_stats_prewarm_job() -> int:
    """Prewarm MTD cache for all valid provinces. Returns number of provinces processed."""
    import time
    today = datetime.today().date()
    start_ts = time.time()
    count = 0
    for province in VALID_PROVINCES:
        try:
            status = prewarm_mtd_province(province, today=today)
            logger.info("Province stats prewarm %s: %s", province, status)
            count += 1
        except Exception as e:
            logger.exception("Province stats prewarm failed for %s: %s", province, e)
    logger.info(
        "Province stats prewarm finished: %d/%d provinces in %.1fs",
        count,
        len(VALID_PROVINCES),
        time.time() - start_ts,
    )
    return count
