from __future__ import annotations

import json
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app import db
from app.blueprints.student_export import bp
from app.blueprints.student_export.services import (
    MAPPABLE_FIELDS,
    OUTPUT_COLUMNS,
    StudentExportError,
    absolute_stored_path,
    analyze_upload,
    discard_staged_upload,
    ensure_schema,
    load_staged_upload,
    persist_run_files,
    resolve_display_name,
    summaries_as_dicts,
    transform_workbook_path,
)
from app.models import StudentExportRun


def _admin_only() -> bool:
    return getattr(current_user, "userRole", None) == "Admin"


def _wants_json() -> bool:
    if request.is_json:
        return True
    accept = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return accept == "application/json"


@bp.route("/", methods=["GET"])
@login_required
def index():
    if not _admin_only():
        return "Unauthorized", 403
    ensure_schema()
    history = (
        StudentExportRun.query.order_by(StudentExportRun.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "student_export/index.html",
        current_month_label=datetime.now().strftime("%B"),
        title="Student Export",
        expected_columns=OUTPUT_COLUMNS,
        mappable_fields=MAPPABLE_FIELDS,
        history=history,
    )


@bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    if not _admin_only():
        return jsonify({"error": "Unauthorized"}), 403
    ensure_schema()
    upload = request.files.get("file")
    try:
        analysis = analyze_upload(upload)
    except StudentExportError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not analyze workbook: {exc}"}), 500
    return jsonify({"ok": True, **analysis})


@bp.route("/run", methods=["POST"])
@login_required
def run_export():
    if not _admin_only():
        if _wants_json():
            return jsonify({"error": "Unauthorized"}), 403
        return "Unauthorized", 403

    ensure_schema()
    token = (request.form.get("token") or "").strip()
    display_override = (request.form.get("display_name") or "").strip()
    try:
        selected_sheets = json.loads(request.form.get("selected_sheets") or "[]")
        mapping = json.loads(request.form.get("mapping") or "{}")
    except json.JSONDecodeError:
        message = "Invalid sheet or column mapping payload."
        if _wants_json():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("student_export.index"))

    if not isinstance(selected_sheets, list) or not selected_sheets:
        message = "Select at least one sheet to process."
        if _wants_json():
            return jsonify({"error": message}), 400
        flash(message, "error")
        return redirect(url_for("student_export.index"))

    try:
        staged_path, original_filename = load_staged_upload(token)
        processed, summaries = transform_workbook_path(
            staged_path,
            selected_sheets,
            mapping,
        )
        display_name = resolve_display_name(original_filename, display_override)
        rel_original, _orig_stored, rel_processed, processed_stored = persist_run_files(
            original_path=staged_path,
            processed_bytes=processed,
            original_filename=original_filename,
            display_name=display_name,
        )
        run = StudentExportRun(
            display_name=display_name,
            original_filename=original_filename,
            original_path=rel_original,
            processed_filename=processed_stored,
            processed_path=rel_processed,
            selected_sheets=selected_sheets,
            column_mapping=mapping,
            summaries=summaries_as_dicts(summaries),
            created_by=getattr(current_user, "id", None),
        )
        db.session.add(run)
        db.session.commit()
        discard_staged_upload(token)
    except StudentExportError as exc:
        db.session.rollback()
        if _wants_json():
            return jsonify({"error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(url_for("student_export.index"))
    except Exception as exc:
        db.session.rollback()
        message = f"Could not process workbook: {exc}"
        if _wants_json():
            return jsonify({"error": message}), 500
        flash(message, "error")
        return redirect(url_for("student_export.index"))

    processed.seek(0)
    return send_file(
        processed,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=display_name,
    )


@bp.route("/history/<int:run_id>/original")
@login_required
def download_original(run_id: int):
    if not _admin_only():
        return "Unauthorized", 403
    ensure_schema()
    run = StudentExportRun.query.get_or_404(run_id)
    return _send_stored(run.original_path, run.original_filename)


@bp.route("/history/<int:run_id>/processed")
@login_required
def download_processed(run_id: int):
    if not _admin_only():
        return "Unauthorized", 403
    ensure_schema()
    run = StudentExportRun.query.get_or_404(run_id)
    return _send_stored(run.processed_path, run.display_name)


def _send_stored(relative_path: str, download_name: str):
    try:
        path = absolute_stored_path(relative_path)
    except StudentExportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("student_export.index"))
    if not path.is_file():
        flash("That stored file is no longer available.", "error")
        return redirect(url_for("student_export.index"))
    return send_file(
        path,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=download_name if download_name.lower().endswith(".xlsx") else f"{download_name}.xlsx",
    )
