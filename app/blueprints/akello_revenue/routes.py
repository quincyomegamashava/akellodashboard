"""Akello Revenue API routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Response, jsonify, request
from flask_login import current_user

from app import db
from app.blueprints.akello_revenue import bp
from app.blueprints.akello_revenue.models import AkelloRevenueMonth, AkelloRevenuePeriod
from app.blueprints.akello_revenue.services import (
    MONTH_NAMES,
    apply_imported_months,
    apply_month_payload,
    build_period_report_bytes,
    build_period_template_bytes,
    can_edit_akello_revenue,
    edit_required,
    find_period_by_code,
    parse_akello_revenue_workbook,
    period_to_dict,
    run_akello_revenue_digest,
    seed_fy2027_if_empty,
    view_required,
)


def _parse_month(val: Any) -> Optional[int]:
    try:
        m = int(val)
    except (TypeError, ValueError):
        return None
    if m < 1 or m > 12:
        return None
    return m


@bp.route("/periods", methods=["GET"])
@view_required
def list_periods():
    seed_fy2027_if_empty()
    periods = AkelloRevenuePeriod.query.order_by(AkelloRevenuePeriod.code.desc()).all()
    return jsonify(
        {
            "success": True,
            "periods": [period_to_dict(p) for p in periods],
            "can_edit": can_edit_akello_revenue(),
        }
    )


@bp.route("/periods/<string:code>", methods=["GET"])
@view_required
def get_period(code: str):
    seed_fy2027_if_empty()
    period = find_period_by_code(code)
    if not period:
        return jsonify({"success": False, "error": "Period not found"}), 404
    return jsonify(
        {
            "success": True,
            "period": period_to_dict(period, include_months=True),
            "can_edit": can_edit_akello_revenue(),
            "month_names": MONTH_NAMES,
        }
    )


@bp.route("/periods", methods=["POST"])
@edit_required
def create_period():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip() or code
    if not code:
        return jsonify({"success": False, "error": "code is required"}), 400
    if AkelloRevenuePeriod.query.filter_by(code=code).first():
        return jsonify({"success": False, "error": "Period already exists"}), 409

    zig = data.get("zig_usd_rate")
    period = AkelloRevenuePeriod(
        code=code,
        name=name,
        zig_usd_rate=zig if zig not in (None, "") else None,
        created_by=getattr(current_user, "id", None),
    )
    db.session.add(period)
    db.session.commit()
    return jsonify({"success": True, "period": period_to_dict(period, include_months=True)}), 201


@bp.route("/periods/<string:code>/months", methods=["POST"])
@edit_required
def add_month(code: str):
    period = find_period_by_code(code)
    if not period:
        return jsonify({"success": False, "error": "Period not found"}), 404

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    month = _parse_month(data.get("month"))
    if month is None:
        return jsonify({"success": False, "error": "month must be 1–12"}), 400

    existing = AkelloRevenueMonth.query.filter_by(period_id=period.id, month=month).first()
    if existing:
        return jsonify({"success": False, "error": "Month already exists; use PUT to update"}), 409

    row = AkelloRevenueMonth(
        period_id=period.id,
        month=month,
        updated_by=getattr(current_user, "id", None),
    )
    apply_month_payload(row, data)
    db.session.add(row)
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "period": period_to_dict(period, include_months=True),
        }
    ), 201


@bp.route("/periods/<string:code>/months/<int:month>", methods=["PUT"])
@edit_required
def upsert_month(code: str, month: int):
    if month < 1 or month > 12:
        return jsonify({"success": False, "error": "month must be 1–12"}), 400

    period = find_period_by_code(code)
    if not period:
        return jsonify({"success": False, "error": "Period not found"}), 404

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    row = AkelloRevenueMonth.query.filter_by(period_id=period.id, month=month).first()
    created = False
    if not row:
        row = AkelloRevenueMonth(period_id=period.id, month=month)
        created = True
        db.session.add(row)

    apply_month_payload(row, data)
    row.updated_by = getattr(current_user, "id", None)
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "created": created,
            "period": period_to_dict(period, include_months=True),
        }
    )


@bp.route("/periods/<string:code>/import", methods=["POST"])
@edit_required
def import_period_workbook(code: str):
    period = find_period_by_code(code)
    if not period:
        return jsonify({"success": False, "error": "Period not found"}), 404

    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"success": False, "error": "file is required"}), 400
    if not upload.filename.lower().endswith(".xlsx"):
        return jsonify({"success": False, "error": "Only .xlsx files are supported"}), 400

    mode = (request.form.get("mode") or request.args.get("mode") or "upsert").strip().lower()
    if mode not in ("upsert", "replace"):
        return jsonify({"success": False, "error": "mode must be upsert or replace"}), 400

    try:
        parsed = parse_akello_revenue_workbook(upload)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "error": f"Failed to parse workbook: {exc}"}), 400

    months = parsed.get("months") or []
    errors = parsed.get("errors") or []
    if not months:
        return jsonify(
            {
                "success": False,
                "error": "No month rows found in workbook",
                "errors": errors,
            }
        ), 400

    result = apply_imported_months(
        period,
        months,
        mode=mode,
        user_id=getattr(current_user, "id", None),
    )
    return jsonify(
        {
            "success": True,
            "applied": result["applied"],
            "deleted": result["deleted"],
            "skipped": 0,
            "errors": errors,
            "period": period_to_dict(period, include_months=True),
        }
    )


@bp.route("/periods/<string:code>/template.xlsx", methods=["GET"])
@view_required
def download_period_template(code: str):
    period = find_period_by_code(code)
    payload = build_period_template_bytes(period)
    filename = f"akello_revenue_template_{(period.code if period else code)}.xlsx"
    return Response(
        payload,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/periods/<string:code>/report.xlsx", methods=["GET"])
@view_required
def download_period_report(code: str):
    """Download selected FY period workbook as shown on the UI."""
    period = find_period_by_code(code)
    if not period:
        return jsonify({"success": False, "error": "Period not found"}), 404
    payload = build_period_report_bytes(period)
    filename = f"Akello_Revenue_{period.code}.xlsx"
    return Response(
        payload,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/digest/run", methods=["POST"])
@edit_required
def run_digest_now():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    period_code = (data.get("period_code") or request.args.get("period") or "").strip() or None
    result = run_akello_revenue_digest(
        triggered_by=f"user:{getattr(current_user, 'username', 'admin')}",
        period_code=period_code,
    )
    status_code = 200 if result.get("status") in ("success", "partial", "skipped") else 500
    return jsonify({"success": result.get("status") != "failed", **result}), status_code
