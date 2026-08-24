"""Extended PM platform routes (roadmap phases 1–6)."""
import json
from datetime import datetime

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import app, db
from app.models import (
    ColumnA,
    MilestoneA,
    ProjectA,
    ProjectABaseline,
    ProjectACustomField,
    ProjectASavedView,
    ProjectASubscription,
    ProjectAWebhook,
    ProjectAWebhookDelivery,
    ProgramA,
    TaskA,
    TaskACustomFieldValue,
    TaskADependency,
    TaskALabel,
    TaskATimeEntry,
    TaskAComment,
    TaskAActivity,
    Notification,
    User,
    taska_comment_mentions,
)
from app.pm_service import (
    baseline_snapshot,
    capture_stats_snapshot,
    clone_project,
    custom_field_to_dict,
    dependency_cycle_exists,
    fire_webhooks,
    get_member_role,
    highlight_mentions_html,
    milestone_to_dict,
    parse_mentions,
    parse_workflow_rules,
    portfolio_stats_for_projects,
    portfolio_export_payload,
    search_tasks_globally,
    sync_primary_blocker,
    task_is_complete,
    task_progress_value,
    validate_column_workflow,
    workload_summary_for_projects,
)


def _import_pm_helpers():
    from app.routes import (
        can_manage_project_a,
        comment_to_dict,
        label_to_dict,
        project_access_denied,
        projects_visible_to_user,
        task_to_dict,
        user_can_access_project_a,
        _log_task_activity,
        _project_for_task,
        _task_a_with_access,
    )
    return locals()


@app.route("/api/projects/<int:project_id>/labels/<int:label_id>", methods=["PATCH", "DELETE"])
@login_required
def project_a_label_detail(project_id, label_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    lbl = TaskALabel.query.filter_by(id=label_id, project_id=p.id).first_or_404()
    if request.method == "DELETE":
        db.session.delete(lbl)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json() or {}
    if "name" in data:
        lbl.name = (data["name"] or "").strip() or lbl.name
    if "color" in data:
        lbl.color = data["color"]
    db.session.commit()
    return jsonify(h["label_to_dict"](lbl))


@app.route("/api/pm/search", methods=["GET"])
@login_required
def pm_global_search():
    q = request.args.get("q", "")
    assignee = request.args.get("assignee", "")
    status = request.args.get("status", "")
    rows = search_tasks_globally(
        current_user,
        q=q,
        assignee_me=(assignee == "me"),
        status=status,
    )
    return jsonify(rows)


@app.route("/api/projects/<int:project_id>/saved-views", methods=["GET", "POST"])
@login_required
def project_saved_views(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        views = ProjectASavedView.query.filter_by(
            project_id=p.id, user_id=current_user.id
        ).order_by(ProjectASavedView.name).all()
        return jsonify([
            {"id": v.id, "name": v.name, "filter_json": json.loads(v.filter_json)}
            for v in views
        ])
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    filt = data.get("filter") or data.get("filter_json")
    if not name or filt is None:
        return jsonify({"error": "name and filter required"}), 400
    v = ProjectASavedView(
        project_id=p.id,
        user_id=current_user.id,
        name=name,
        filter_json=json.dumps(filt),
    )
    db.session.add(v)
    db.session.commit()
    return jsonify({"id": v.id, "name": v.name, "filter_json": filt}), 201


@app.route("/api/projects/<int:project_id>/saved-views/<int:view_id>", methods=["DELETE"])
@login_required
def delete_saved_view(project_id, view_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    v = ProjectASavedView.query.filter_by(id=view_id, project_id=p.id, user_id=current_user.id).first_or_404()
    db.session.delete(v)
    db.session.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/projects/<int:project_id>/custom-fields", methods=["GET", "POST"])
@login_required
def project_custom_fields(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        fields = ProjectACustomField.query.filter_by(project_id=p.id).order_by(
            ProjectACustomField.position
        ).all()
        return jsonify([custom_field_to_dict(f) for f in fields])
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    maxpos = db.session.query(db.func.max(ProjectACustomField.position)).filter_by(project_id=p.id).scalar()
    cf = ProjectACustomField(
        project_id=p.id,
        name=name,
        field_type=data.get("field_type", "text"),
        options_json=json.dumps(data.get("options") or []),
        required_on_close=bool(data.get("required_on_close")),
        position=(maxpos + 1) if maxpos is not None else 0,
    )
    db.session.add(cf)
    db.session.commit()
    return jsonify(custom_field_to_dict(cf)), 201


@app.route("/api/projects/<int:project_id>/custom-fields/<int:field_id>", methods=["PATCH", "DELETE"])
@login_required
def project_custom_field_detail(project_id, field_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    cf = ProjectACustomField.query.filter_by(id=field_id, project_id=p.id).first_or_404()
    if request.method == "DELETE":
        db.session.delete(cf)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json() or {}
    for key in ("name", "field_type", "required_on_close", "position"):
        if key in data:
            setattr(cf, key, data[key])
    if "options" in data:
        cf.options_json = json.dumps(data["options"] or [])
    db.session.commit()
    return jsonify(custom_field_to_dict(cf))


@app.route("/api/columns/<int:column_id>/workflow", methods=["GET", "PATCH"])
@login_required
def column_workflow(column_id):
    h = _import_pm_helpers()
    col = ColumnA.query.get_or_404(column_id)
    p = col.project
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        return jsonify(parse_workflow_rules(col))
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    col.workflow_rules = json.dumps(data)
    db.session.commit()
    return jsonify(data)


@app.route("/api/tasks/<int:task_id>/dependencies", methods=["GET", "POST"])
@login_required
def task_dependencies(task_id):
    h = _import_pm_helpers()
    t = h["_task_a_with_access"](task_id)
    p = h["_project_for_task"](t)
    if request.method == "GET":
        deps = TaskADependency.query.filter_by(task_id=t.id).all()
        return jsonify([
            {"id": d.id, "depends_on_task_id": d.depends_on_task_id, "dep_type": d.dep_type}
            for d in deps
        ])
    data = request.get_json() or {}
    dep_id = data.get("depends_on_task_id")
    if not dep_id:
        return jsonify({"error": "depends_on_task_id required"}), 400
    dep_id = int(dep_id)
    if dep_id == t.id:
        return jsonify({"error": "Cannot depend on self"}), 400
    blocker = TaskA.query.get(dep_id)
    if not blocker or h["_project_for_task"](blocker).id != p.id:
        return jsonify({"error": "Invalid dependency task"}), 400
    if dependency_cycle_exists(p.id, t.id, dep_id):
        return jsonify({"error": "Dependency would create a cycle"}), 400
    existing = TaskADependency.query.filter_by(task_id=t.id, depends_on_task_id=dep_id).first()
    if existing:
        return jsonify({"id": existing.id, "depends_on_task_id": dep_id}), 200
    d = TaskADependency(task_id=t.id, depends_on_task_id=dep_id, dep_type=data.get("dep_type", "finish_to_start"))
    db.session.add(d)
    sync_primary_blocker(t)
    h["_log_task_activity"](t, "dependency", f"Depends on task #{dep_id}")
    db.session.commit()
    fire_webhooks(p.id, "task.updated", {"task_id": t.id})
    return jsonify({"id": d.id, "depends_on_task_id": dep_id}), 201


@app.route("/api/tasks/<int:task_id>/dependencies/<int:dep_id>", methods=["DELETE"])
@login_required
def delete_task_dependency(task_id, dep_id):
    h = _import_pm_helpers()
    t = h["_task_a_with_access"](task_id)
    d = TaskADependency.query.filter_by(id=dep_id, task_id=t.id).first_or_404()
    db.session.delete(d)
    sync_primary_blocker(t)
    db.session.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/projects/<int:project_id>/task-dependencies", methods=["GET"])
@login_required
def project_task_dependencies(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    col_ids = [c.id for c in ColumnA.query.filter_by(project_id=p.id).all()]
    if not col_ids:
        return jsonify([])
    task_ids = [t.id for t in TaskA.query.filter(TaskA.column_id.in_(col_ids)).all()]
    if not task_ids:
        return jsonify([])
    deps = TaskADependency.query.filter(TaskADependency.task_id.in_(task_ids)).all()
    return jsonify([
        {"id": d.id, "task_id": d.task_id, "depends_on_task_id": d.depends_on_task_id}
        for d in deps
    ])


@app.route("/api/projects/<int:project_id>/milestones", methods=["GET", "POST"])
@login_required
def project_milestones(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        ms = MilestoneA.query.filter_by(project_id=p.id).order_by(MilestoneA.position).all()
        return jsonify([milestone_to_dict(m) for m in ms])
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    due = data.get("due_date")
    due_dt = datetime.fromisoformat(due) if due else None
    maxpos = db.session.query(db.func.max(MilestoneA.position)).filter_by(project_id=p.id).scalar()
    m = MilestoneA(
        project_id=p.id,
        title=title,
        due_date=due_dt,
        color=data.get("color", "#8b5cf6"),
        position=(maxpos + 1) if maxpos is not None else 0,
    )
    db.session.add(m)
    db.session.flush()
    task_ids = data.get("task_ids") or []
    if task_ids:
        m.tasks = TaskA.query.filter(TaskA.id.in_(task_ids)).all()
    db.session.commit()
    return jsonify(milestone_to_dict(m)), 201


@app.route("/api/projects/<int:project_id>/milestones/<int:ms_id>", methods=["PATCH", "DELETE"])
@login_required
def project_milestone_detail(project_id, ms_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    m = MilestoneA.query.filter_by(id=ms_id, project_id=p.id).first_or_404()
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "DELETE":
        db.session.delete(m)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json() or {}
    if "title" in data:
        m.title = data["title"]
    if "due_date" in data:
        m.due_date = datetime.fromisoformat(data["due_date"]) if data["due_date"] else None
    if "color" in data:
        m.color = data["color"]
    if "task_ids" in data:
        m.tasks = TaskA.query.filter(TaskA.id.in_(data["task_ids"] or [])).all()
    db.session.commit()
    return jsonify(milestone_to_dict(m))


@app.route("/api/projects/<int:project_id>/baselines", methods=["GET", "POST"])
@login_required
def project_baselines(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        rows = ProjectABaseline.query.filter_by(project_id=p.id).order_by(
            ProjectABaseline.created_at.desc()
        ).all()
        return jsonify([
            {
                "id": b.id,
                "name": b.name,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "snapshot": json.loads(b.snapshot_json),
            }
            for b in rows
        ])
    data = request.get_json() or {}
    name = (data.get("name") or f"Baseline {datetime.utcnow().strftime('%Y-%m-%d')}").strip()
    snap = baseline_snapshot(p)
    b = ProjectABaseline(project_id=p.id, name=name, snapshot_json=snap, created_by=current_user.id)
    db.session.add(b)
    db.session.commit()
    return jsonify({"id": b.id, "name": b.name, "snapshot": json.loads(snap)}), 201


@app.route("/api/pm/portfolio", methods=["GET"])
@login_required
def pm_portfolio():
    projects = _import_pm_helpers()["projects_visible_to_user"]()
    program_id = request.args.get("program_id")
    if program_id:
        prog = ProgramA.query.get(int(program_id))
        if prog:
            pid_set = {p.id for p in prog.projects}
            projects = [p for p in projects if p.id in pid_set]
    stats = portfolio_stats_for_projects(projects)
    health = request.args.get("health")
    if health in ("red", "yellow", "green"):
        stats = [s for s in stats if s.get("health") == health]
    return jsonify(stats)


@app.route("/api/pm/portfolio/export-detail", methods=["GET"])
@login_required
def pm_portfolio_export_detail():
    projects = _import_pm_helpers()["projects_visible_to_user"]()
    program_id = request.args.get("program_id")
    if program_id:
        prog = ProgramA.query.get(int(program_id))
        if prog:
            pid_set = {p.id for p in prog.projects}
            projects = [p for p in projects if p.id in pid_set]
    health = request.args.get("health")
    payload = portfolio_export_payload(projects)
    if health in ("red", "yellow", "green"):
        payload = [s for s in payload if s.get("health") == health]
    return jsonify(payload)


@app.route("/pm/portfolio")
@login_required
def pm_portfolio_page():
    return render_template("pm_portfolio.html")


@app.route("/api/pm/programs", methods=["GET", "POST"])
@login_required
def pm_programs():
    if request.method == "GET":
        progs = ProgramA.query.order_by(ProgramA.name).all()
        return jsonify([
            {
                "id": pr.id,
                "name": pr.name,
                "description": pr.description,
                "project_ids": [p.id for p in (pr.projects or [])],
            }
            for pr in progs
        ])
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    pr = ProgramA(name=name, description=data.get("description"))
    db.session.add(pr)
    db.session.flush()
    if data.get("project_ids"):
        pr.projects = ProjectA.query.filter(ProjectA.id.in_(data["project_ids"])).all()
    db.session.commit()
    return jsonify({"id": pr.id, "name": pr.name}), 201


@app.route("/api/pm/programs/<int:prog_id>", methods=["PATCH"])
@login_required
def pm_program_patch(prog_id):
    pr = ProgramA.query.get_or_404(prog_id)
    data = request.get_json() or {}
    if "name" in data and data["name"]:
        pr.name = data["name"].strip()
    if "description" in data:
        pr.description = data.get("description")
    if "project_ids" in data:
        pr.projects = ProjectA.query.filter(ProjectA.id.in_(data["project_ids"] or [])).all()
    db.session.commit()
    return jsonify({
        "id": pr.id,
        "name": pr.name,
        "project_ids": [p.id for p in (pr.projects or [])],
    })


@app.route("/api/projects/<int:project_id>/activities", methods=["GET"])
@login_required
def project_activities(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    since = request.args.get("since")
    col_ids = [c.id for c in ColumnA.query.filter_by(project_id=p.id).all()]
    task_ids = [t.id for t in TaskA.query.filter(TaskA.column_id.in_(col_ids)).all()] if col_ids else []
    if not task_ids:
        return jsonify([])
    q = TaskAActivity.query.filter(TaskAActivity.task_id.in_(task_ids))
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q = q.filter(TaskAActivity.created_at >= since_dt)
        except ValueError:
            pass
    acts = q.order_by(TaskAActivity.created_at.desc()).limit(200).all()
    from app.routes import activity_to_dict
    return jsonify([activity_to_dict(a) for a in acts])


@app.route("/api/projects/<int:project_id>/subscribe", methods=["GET", "POST", "DELETE"])
@login_required
def project_subscribe(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    sub = ProjectASubscription.query.filter_by(project_id=p.id, user_id=current_user.id).first()
    if request.method == "GET":
        return jsonify({"subscribed": sub is not None})
    if request.method == "DELETE":
        if sub:
            db.session.delete(sub)
            db.session.commit()
        return jsonify({"subscribed": False})
    if not sub:
        db.session.add(ProjectASubscription(project_id=p.id, user_id=current_user.id))
        db.session.commit()
    return jsonify({"subscribed": True})


@app.route("/api/tasks/<int:task_id>/time-entries", methods=["GET", "POST"])
@login_required
def task_time_entries(task_id):
    h = _import_pm_helpers()
    t = h["_task_a_with_access"](task_id)
    if request.method == "GET":
        entries = TaskATimeEntry.query.filter_by(task_id=t.id).order_by(TaskATimeEntry.entry_date.desc()).all()
        return jsonify([
            {
                "id": e.id,
                "minutes": e.minutes,
                "entry_date": e.entry_date.isoformat(),
                "note": e.note,
                "user_id": e.user_id,
            }
            for e in entries
        ])
    data = request.get_json() or {}
    minutes = int(data.get("minutes") or 0)
    if minutes <= 0:
        return jsonify({"error": "minutes required"}), 400
    ed = data.get("entry_date")
    entry_date = datetime.fromisoformat(ed).date() if ed else datetime.utcnow().date()
    e = TaskATimeEntry(
        task_id=t.id,
        user_id=current_user.id,
        minutes=minutes,
        entry_date=entry_date,
        note=data.get("note"),
    )
    db.session.add(e)
    db.session.commit()
    return jsonify({"id": e.id, "minutes": minutes}), 201


@app.route("/api/tasks/<int:task_id>/time-entries/<int:entry_id>", methods=["PATCH", "DELETE"])
@login_required
def task_time_entry_item(task_id, entry_id):
    h = _import_pm_helpers()
    t = h["_task_a_with_access"](task_id)
    p = h["_project_for_task"](t)
    e = TaskATimeEntry.query.filter_by(id=entry_id, task_id=t.id).first_or_404()
    if e.user_id != current_user.id and not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    if request.method == "DELETE":
        db.session.delete(e)
        db.session.commit()
        return jsonify({"status": "deleted"})
    data = request.get_json() or {}
    if "minutes" in data:
        minutes = int(data.get("minutes") or 0)
        if minutes <= 0:
            return jsonify({"error": "minutes must be positive"}), 400
        e.minutes = minutes
    if "entry_date" in data and data.get("entry_date"):
        e.entry_date = datetime.fromisoformat(data["entry_date"]).date()
    if "note" in data:
        e.note = data.get("note")
    db.session.commit()
    return jsonify({
        "id": e.id,
        "minutes": e.minutes,
        "entry_date": e.entry_date.isoformat(),
        "note": e.note,
        "user_id": e.user_id,
    })


@app.route("/api/projects/<int:project_id>/webhooks", methods=["GET", "POST"])
@login_required
def project_webhooks(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    if request.method == "GET":
        hooks = ProjectAWebhook.query.filter_by(project_id=p.id).all()
        return jsonify([
            {"id": wh.id, "url": wh.url, "events": json.loads(wh.events_json or "[]"), "active": wh.active}
            for wh in hooks
        ])
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    wh = ProjectAWebhook(
        project_id=p.id,
        url=url,
        events_json=json.dumps(data.get("events") or ["task.moved"]),
        secret=data.get("secret"),
        active=bool(data.get("active", True)),
    )
    db.session.add(wh)
    db.session.commit()
    return jsonify({"id": wh.id}), 201


@app.route("/api/projects/<int:project_id>/webhooks/<int:wh_id>/deliveries", methods=["GET"])
@login_required
def project_webhook_deliveries(project_id, wh_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    wh = ProjectAWebhook.query.filter_by(id=wh_id, project_id=p.id).first_or_404()
    rows = (
        ProjectAWebhookDelivery.query.filter_by(webhook_id=wh.id)
        .order_by(ProjectAWebhookDelivery.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify([
        {
            "id": d.id,
            "event": d.event,
            "status_code": d.status_code,
            "error": d.error,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ])


@app.route("/api/projects/<int:project_id>/webhooks/<int:wh_id>/test", methods=["POST"])
@login_required
def project_webhook_test(project_id, wh_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    wh = ProjectAWebhook.query.filter_by(id=wh_id, project_id=p.id).first_or_404()
    fire_webhooks(
        p.id,
        "webhook.test",
        {"project_id": p.id, "message": "Test ping from Akello PM"},
        webhook_id=wh.id,
    )
    latest = (
        ProjectAWebhookDelivery.query.filter_by(webhook_id=wh.id)
        .order_by(ProjectAWebhookDelivery.created_at.desc())
        .first()
    )
    return jsonify({
        "status_code": latest.status_code if latest else None,
        "error": latest.error if latest else None,
    })


@app.route("/api/pm/workload", methods=["GET"])
@login_required
def pm_workload():
    projects = _import_pm_helpers()["projects_visible_to_user"]()
    return jsonify(workload_summary_for_projects(projects))


@app.route("/pm/workload")
@login_required
def pm_workload_page():
    return render_template("pm_workload.html")


@app.route("/api/projects/<int:project_id>/members/roles", methods=["GET", "PATCH"])
@login_required
def project_member_roles(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["can_manage_project_a"](p):
        return jsonify({"error": "Forbidden"}), 403
    if request.method == "GET":
        rows = []
        for u in p.members:
            rows.append({"user_id": u.id, "name": u.username, "role": get_member_role(p, u.id) or "contributor"})
        return jsonify(rows)
    data = request.get_json() or {}
    user_id = data.get("user_id")
    role = data.get("role", "contributor")
    if role not in ("viewer", "contributor", "admin"):
        return jsonify({"error": "Invalid role"}), 400
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db.session.execute(
        db.text(
            "UPDATE project_membersa SET role = :role WHERE project_id = :pid AND user_id = :uid"
        ),
        {"role": role, "pid": p.id, "uid": int(user_id)},
    )
    db.session.commit()
    return jsonify({"status": "ok"})


@app.route("/api/projects/<int:project_id>/stats/snapshots", methods=["GET", "POST"])
@login_required
def project_stats_snapshots(project_id):
    h = _import_pm_helpers()
    p = ProjectA.query.get_or_404(project_id)
    if not h["user_can_access_project_a"](p):
        return h["project_access_denied"]()
    if request.method == "GET":
        from app.models import ProjectAStatsSnapshot
        snaps = ProjectAStatsSnapshot.query.filter_by(project_id=p.id).order_by(
            ProjectAStatsSnapshot.snapshot_date
        ).limit(52).all()
        return jsonify([
            {
                "date": s.snapshot_date.isoformat(),
                "total": s.total_tasks,
                "completed": s.completed_tasks,
                "overdue": s.overdue_tasks,
            }
            for s in snaps
        ])
    snap = capture_stats_snapshot(project_id)
    db.session.commit()
    return jsonify({
        "date": snap.snapshot_date.isoformat(),
        "total": snap.total_tasks,
        "completed": snap.completed_tasks,
    }), 201

