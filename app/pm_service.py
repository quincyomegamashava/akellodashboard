"""Project management business logic (shared by routes)."""
import json
import re
from collections import defaultdict, deque
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    ColumnA,
    MilestoneA,
    ProjectA,
    ProjectABaseline,
    ProjectACustomField,
    ProjectAStatsSnapshot,
    ProjectAWebhook,
    ProgramA,
    TaskA,
    TaskACustomFieldValue,
    TaskADependency,
    TaskALabel,
    TaskASubtask,
    User,
    project_membersA,
    taska_comment_mentions,
)


def parse_workflow_rules(col):
    if not col or not col.workflow_rules:
        return {}
    try:
        return json.loads(col.workflow_rules) or {}
    except (TypeError, ValueError):
        return {}


def validate_column_workflow(task, dest_col):
    """Return error message if task cannot move to dest_col, else None."""
    rules = parse_workflow_rules(dest_col)
    if rules:
        if rules.get("require_assignee") and not (task.assignees or []):
            return "This column requires an assignee."
        if rules.get("require_due_date") and not task.end_date:
            return "This column requires a due date."
        min_prog = rules.get("min_progress")
        if min_prog is not None:
            prog = task_progress_value(task)
            if prog < int(min_prog):
                return f"This column requires at least {min_prog}% progress."
    cf_err = validate_custom_fields_on_close(task, dest_col)
    if cf_err:
        return cf_err
    return None


def validate_custom_fields_on_close(task, dest_col):
    """Require custom fields marked required_on_close when moving to Done/Complete."""
    title_lower = (dest_col.title or "").lower()
    if "done" not in title_lower and "complete" not in title_lower:
        return None
    fields = ProjectACustomField.query.filter_by(
        project_id=dest_col.project_id, required_on_close=True
    ).all()
    if not fields:
        return None
    values = {
        v.field_id: v
        for v in TaskACustomFieldValue.query.filter_by(task_id=task.id).all()
    }
    missing = []
    for f in fields:
        v = values.get(f.id)
        if not v or not (v.value_text or "").strip():
            missing.append(f.name)
    if missing:
        return "Required fields before completing: " + ", ".join(missing)
    return None


def task_progress_value(task):
    subtasks = getattr(task, "subtasks", None) or []
    if subtasks:
        done = sum(1 for s in subtasks if s.is_done)
        return int(round(100 * done / len(subtasks)))
    return task.progress or 0


def task_is_complete(task):
    return task_progress_value(task) >= 100


def dependency_cycle_exists(project_id, task_id, depends_on_id, exclude_dep_id=None):
    """Detect if adding task_id -> depends_on_id would create a cycle."""
    deps = TaskADependency.query.join(TaskA, TaskADependency.task_id == TaskA.id).join(
        ColumnA, TaskA.column_id == ColumnA.id
    ).filter(ColumnA.project_id == project_id).all()
    graph = defaultdict(set)
    for d in deps:
        if exclude_dep_id and d.id == exclude_dep_id:
            continue
        graph[d.task_id].add(d.depends_on_task_id)
    graph[task_id].add(depends_on_id)
    visited = set()
    stack = [task_id]

    def dfs(node, path):
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        for nxt in graph.get(node, ()):
            if dfs(nxt, path | {node}):
                return True
        return False

    return dfs(task_id, set())


def sync_primary_blocker(task):
    """Set blocked_by_task_id from first incomplete dependency."""
    deps = TaskADependency.query.filter_by(task_id=task.id).all()
    primary = None
    for d in deps:
        blocker = TaskA.query.get(d.depends_on_task_id)
        if blocker and not task_is_complete(blocker):
            primary = blocker.id
            break
    task.blocked_by_task_id = primary


def clone_project(source, name, owner_id, include_tasks=False):
    """Clone project columns, labels, and optionally tasks."""
    p = ProjectA(name=name, project_type=source.project_type, owner_id=owner_id)
    db.session.add(p)
    db.session.flush()

    label_map = {}
    for lbl in TaskALabel.query.filter_by(project_id=source.id).all():
        nl = TaskALabel(project_id=p.id, name=lbl.name, color=lbl.color)
        db.session.add(nl)
        db.session.flush()
        label_map[lbl.id] = nl.id

    col_map = {}
    task_map = {}
    for col in ColumnA.query.filter_by(project_id=source.id).order_by(ColumnA.position).all():
        nc = ColumnA(
            project_id=p.id,
            title=col.title,
            position=col.position,
            workflow_rules=col.workflow_rules,
        )
        db.session.add(nc)
        db.session.flush()
        col_map[col.id] = nc.id

        if include_tasks:
            for t in sorted(col.tasks, key=lambda x: x.position):
                nt = TaskA(
                    column_id=nc.id,
                    title=t.title,
                    description=t.description,
                    position=t.position,
                    progress=t.progress,
                    priority=t.priority,
                    start_date=t.start_date,
                    end_date=t.end_date,
                    date_rollup_enabled=t.date_rollup_enabled,
                    created_by=owner_id,
                )
                db.session.add(nt)
                db.session.flush()
                task_map[t.id] = nt.id
                if t.labels:
                    nt.labels = [
                        TaskALabel.query.get(label_map[l.id])
                        for l in t.labels
                        if l.id in label_map
                    ]

    for cf in ProjectACustomField.query.filter_by(project_id=source.id).order_by(ProjectACustomField.position).all():
        db.session.add(ProjectACustomField(
            project_id=p.id,
            name=cf.name,
            field_type=cf.field_type,
            options_json=cf.options_json,
            required_on_close=cf.required_on_close,
            position=cf.position,
        ))

    db.session.flush()
    return p, col_map, task_map


def parse_mentions(body, project):
    """Return list of User objects mentioned via @username in body."""
    if not body:
        return []
    names = set(re.findall(r"@([A-Za-z0-9_.-]+)", body))
    if not names:
        return []
    member_ids = {u.id for u in project.members}
    if project.owner_id:
        member_ids.add(project.owner_id)
    users = []
    for uname in names:
        u = User.query.filter_by(username=uname).first()
        if u and u.id in member_ids:
            users.append(u)
    return users


def highlight_mentions_html(body):
    if not body:
        return ""
    return re.sub(
        r"@([A-Za-z0-9_.-]+)",
        r'<span class="pm-mention">@\1</span>',
        body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
    )


def search_tasks_globally(user, q="", assignee_me=False, status="", limit=40):
    """Search tasks across projects visible to user (DB filters + hard limit)."""
    from sqlalchemy import or_
    from app.routes import projects_visible_to_user

    q = (q or "").strip()
    visible = projects_visible_to_user()
    visible_ids = [p.id for p in visible]
    if not visible_ids:
        return []

    cols = ColumnA.query.filter(ColumnA.project_id.in_(visible_ids)).all()
    if not cols:
        return []
    col_by_id = {c.id: c for c in cols}
    project_by_id = {p.id: p for p in visible}
    col_ids = list(col_by_id.keys())

    query = (
        TaskA.query.options(joinedload(TaskA.assignees))
        .filter(TaskA.column_id.in_(col_ids))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(or_(TaskA.title.ilike(like), TaskA.description.ilike(like)))
    me_id = user.id if user else None
    if assignee_me and me_id:
        query = query.filter(TaskA.assignees.any(User.id == me_id))

    # Over-fetch slightly so open/done filters still yield enough rows.
    tasks = query.order_by(TaskA.id.desc()).limit(max(limit * 5, 100)).all()

    rows = []
    for task in tasks:
        col = col_by_id.get(task.column_id)
        if not col:
            continue
        project = project_by_id.get(col.project_id)
        if not project:
            continue
        prog = task_progress_value(task)
        is_open = prog < 100
        if status == "open" and not is_open:
            continue
        if status == "done" and is_open:
            continue
        rows.append({
            "task_id": task.id,
            "title": task.title,
            "project_id": project.id,
            "project_name": project.name,
            "column_title": col.title,
            "progress": prog,
            "end_date": task.end_date.isoformat() if task.end_date else None,
        })
        if len(rows) >= limit:
            break

    rows.sort(key=lambda r: (r["project_name"], r["title"]))
    return rows


def portfolio_stats_for_projects(projects):
    today = datetime.utcnow().date()
    now = datetime.utcnow()
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    all_cols = ColumnA.query.filter(ColumnA.project_id.in_(project_ids)).all()
    cols_by_project = {}
    col_by_id = {}
    for c in all_cols:
        cols_by_project.setdefault(c.project_id, []).append(c)
        col_by_id[c.id] = c
    all_col_ids = list(col_by_id.keys())

    all_tasks = (
        TaskA.query.options(joinedload(TaskA.assignees))
        .filter(TaskA.column_id.in_(all_col_ids))
        .all()
        if all_col_ids
        else []
    )
    tasks_by_project = {pid: [] for pid in project_ids}
    blocker_ids = set()
    for t in all_tasks:
        col = col_by_id.get(t.column_id)
        if not col:
            continue
        tasks_by_project.setdefault(col.project_id, []).append(t)
        if t.blocked_by_task_id:
            blocker_ids.add(t.blocked_by_task_id)

    blockers = {}
    if blocker_ids:
        blockers = {
            b.id: b
            for b in TaskA.query.filter(TaskA.id.in_(list(blocker_ids))).all()
        }

    milestones = (
        MilestoneA.query.filter(
            MilestoneA.project_id.in_(project_ids),
            MilestoneA.due_date.isnot(None),
            MilestoneA.due_date >= now,
        )
        .order_by(MilestoneA.due_date)
        .all()
    )
    next_ms_by_project = {}
    for m in milestones:
        if m.project_id not in next_ms_by_project:
            next_ms_by_project[m.project_id] = m

    owner_ids = {p.owner_id for p in projects if p.owner_id}
    owners = {}
    if owner_ids:
        owners = {u.id: u for u in User.query.filter(User.id.in_(list(owner_ids))).all()}

    stats = []
    for p in projects:
        tasks = tasks_by_project.get(p.id) or []
        total = len(tasks)
        done = sum(1 for t in tasks if task_is_complete(t))
        open_count = total - done
        overdue = 0
        blocked = 0
        top_overdue = []
        for t in tasks:
            prog = task_progress_value(t)
            if t.end_date and t.end_date.date() < today and prog < 100:
                overdue += 1
                if len(top_overdue) < 5:
                    col = col_by_id.get(t.column_id)
                    top_overdue.append({
                        "task_id": t.id,
                        "title": t.title,
                        "due_date": t.end_date.isoformat() if t.end_date else None,
                        "assignees": [u.username for u in (t.assignees or [])],
                        "column_title": col.title if col else "",
                    })
            if t.blocked_by_task_id:
                blocker = blockers.get(t.blocked_by_task_id)
                if blocker and not task_is_complete(blocker):
                    blocked += 1
        top_overdue.sort(key=lambda x: x.get("due_date") or "9999")
        pct = int(round(100 * done / total)) if total else 0
        health = "green"
        if overdue > 0 or (total and blocked > total * 0.2):
            health = "red"
        elif blocked > 0 or pct < 50:
            health = "yellow"
        next_ms = next_ms_by_project.get(p.id)
        owner = owners.get(p.owner_id) if p.owner_id else None
        program_names = [pr.name for pr in (p.programs or [])]
        stats.append({
            "project_id": p.id,
            "project_name": p.name,
            "project_type": p.project_type,
            "owner_id": p.owner_id,
            "owner_name": owner.username if owner else None,
            "program_names": program_names,
            "total_tasks": total,
            "completed_tasks": done,
            "open_task_count": open_count,
            "pct_complete": pct,
            "overdue_count": overdue,
            "blocked_count": blocked,
            "health": health,
            "next_milestone": next_ms.title if next_ms else None,
            "next_milestone_date": next_ms.due_date.isoformat() if next_ms and next_ms.due_date else None,
            "top_overdue_tasks": top_overdue,
        })
    return stats


def workload_summary_for_projects(projects):
    """Per-user open/overdue/blocked counts and sample tasks across projects."""
    today = datetime.utcnow().date()
    by_user = {}

    def user_key(u):
        return u.id if u else 0

    def get_row(u):
        uid = user_key(u)
        if uid not in by_user:
            by_user[uid] = {
                "user_id": uid or None,
                "user_name": u.username if u else "Unassigned",
                "open_count": 0,
                "overdue_count": 0,
                "blocked_count": 0,
                "projects": {},
                "sample_tasks": [],
            }
        return by_user[uid]

    def bump(u, project, kind, task_row=None):
        row = get_row(u)
        row[f"{kind}_count"] += 1
        pmap = row["projects"]
        if project.id not in pmap:
            pmap[project.id] = {
                "project_id": project.id,
                "project_name": project.name,
                "open": 0,
                "overdue": 0,
                "blocked": 0,
            }
        pmap[project.id][kind] += 1
        if task_row and len(row["sample_tasks"]) < 8:
            row["sample_tasks"].append(task_row)

    for p in projects:
        cols = ColumnA.query.filter_by(project_id=p.id).all()
        col_by_id = {c.id: c for c in cols}
        col_ids = list(col_by_id.keys())
        tasks = (
            TaskA.query.options(joinedload(TaskA.assignees))
            .filter(TaskA.column_id.in_(col_ids))
            .all()
            if col_ids else []
        )
        for t in tasks:
            prog = task_progress_value(t)
            if prog >= 100:
                continue
            is_overdue = bool(t.end_date and t.end_date.date() < today)
            blocker = TaskA.query.get(t.blocked_by_task_id) if t.blocked_by_task_id else None
            is_blocked = bool(blocker and not task_is_complete(blocker))
            col = col_by_id.get(t.column_id)
            task_row = {
                "task_id": t.id,
                "title": t.title,
                "project_id": p.id,
                "project_name": p.name,
                "column_title": col.title if col else "",
                "progress": prog,
                "end_date": t.end_date.isoformat() if t.end_date else None,
            }
            assignees = list(t.assignees or [])
            targets = assignees if assignees else [None]
            for u in targets:
                bump(u, p, "open", task_row)
                if is_overdue:
                    bump(u, p, "overdue")
                if is_blocked:
                    bump(u, p, "blocked")

    result = []
    for row in by_user.values():
        result.append({
            **row,
            "projects": list(row["projects"].values()),
        })
    result.sort(key=lambda r: (-r["overdue_count"], -r["open_count"], r["user_name"]))
    return result


def portfolio_export_payload(projects):
    """Rich per-project task and milestone data for manager-facing exports."""
    stats_list = portfolio_stats_for_projects(projects)
    by_id = {p.id: p for p in projects}
    today = datetime.utcnow().date()
    payloads = []
    for s in stats_list:
        p = by_id.get(s["project_id"])
        if not p:
            continue
        cols = ColumnA.query.filter_by(project_id=p.id).order_by(ColumnA.position).all()
        tasks = []
        for col in cols:
            col_tasks = (
                TaskA.query.options(joinedload(TaskA.assignees))
                .filter_by(column_id=col.id)
                .order_by(TaskA.position)
                .all()
            )
            for t in col_tasks:
                prog = task_progress_value(t)
                status = "Complete" if prog >= 100 else "On track"
                if t.end_date and t.end_date.date() < today and prog < 100:
                    status = "Overdue"
                if t.blocked_by_task_id:
                    blocker = TaskA.query.get(t.blocked_by_task_id)
                    if blocker and not task_is_complete(blocker):
                        status = "Blocked"
                tasks.append({
                    "title": t.title,
                    "column": col.title,
                    "progress": prog,
                    "priority": t.priority or "medium",
                    "start_date": t.start_date.isoformat() if t.start_date else None,
                    "end_date": t.end_date.isoformat() if t.end_date else None,
                    "assignees": [u.username for u in (t.assignees or [])],
                    "status": status,
                })
        milestones = [
            milestone_to_dict(m)
            for m in MilestoneA.query.filter_by(project_id=p.id).order_by(MilestoneA.position).all()
        ]
        column_summary = [
            {"title": c.title, "count": TaskA.query.filter_by(column_id=c.id).count()}
            for c in cols
        ]
        payloads.append({
            **s,
            "tasks": tasks,
            "milestones": milestones,
            "columns": column_summary,
        })
    return payloads


def run_pm_due_soon_job():
    """Notify assignees about tasks due within 24 hours."""
    from app.models import Notification
    from flask import url_for

    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)
    cols = ColumnA.query.all()
    col_by_id = {c.id: c for c in cols}
    col_ids = list(col_by_id.keys())
    if not col_ids:
        return 0
    tasks = TaskA.query.filter(
        TaskA.column_id.in_(col_ids),
        TaskA.end_date.isnot(None),
        TaskA.end_date >= now,
        TaskA.end_date <= window_end,
    ).all()
    created = 0
    for t in tasks:
        if task_is_complete(t):
            continue
        col = col_by_id.get(t.column_id)
        if not col:
            continue
        project_id = col.project_id
        for u in (t.assignees or []):
            recent = Notification.query.filter(
                Notification.user_id == u.id,
                Notification.task_id == t.id,
                Notification.notification_type == "pm_due_soon",
                Notification.created_at >= now - timedelta(hours=24),
            ).first()
            if recent:
                continue
            link = url_for("projectmanagement", _external=False) + f"?project={project_id}&task={t.id}"
            db.session.add(Notification(
                user_id=u.id,
                task_id=t.id,
                message=f"Task due soon: {t.title}. {link}",
                notification_type="pm_due_soon",
            ))
            created += 1
    if created:
        db.session.commit()
    return created


def capture_stats_snapshot(project_id):
    p = ProjectA.query.get(project_id)
    if not p:
        return None
    today = date.today()
    existing = ProjectAStatsSnapshot.query.filter_by(
        project_id=project_id, snapshot_date=today
    ).first()
    if existing:
        return existing
    cols = ColumnA.query.filter_by(project_id=p.id).all()
    col_ids = [c.id for c in cols]
    tasks = TaskA.query.filter(TaskA.column_id.in_(col_ids)).all() if col_ids else []
    total = len(tasks)
    done = sum(1 for t in tasks if task_is_complete(t))
    overdue = sum(
        1 for t in tasks
        if t.end_date and t.end_date.date() < today and task_progress_value(t) < 100
    )
    snap = ProjectAStatsSnapshot(
        project_id=project_id,
        snapshot_date=today,
        total_tasks=total,
        completed_tasks=done,
        overdue_tasks=overdue,
    )
    db.session.add(snap)
    return snap


def run_pm_stats_snapshot_job():
    """Weekly job: capture stats snapshot for all projects (dedupe same-day)."""
    today = date.today()
    projects = ProjectA.query.all()
    created = 0
    for p in projects:
        if ProjectAStatsSnapshot.query.filter_by(project_id=p.id, snapshot_date=today).first():
            continue
        if capture_stats_snapshot(p.id):
            created += 1
    if created:
        db.session.commit()
    return created


def baseline_snapshot(project):
    cols = ColumnA.query.filter_by(project_id=project.id).order_by(ColumnA.position).all()
    tasks_data = []
    for col in cols:
        for t in sorted(col.tasks, key=lambda x: x.position):
            tasks_data.append({
                "task_id": t.id,
                "title": t.title,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "progress": task_progress_value(t),
            })
    return json.dumps({"tasks": tasks_data, "captured_at": datetime.utcnow().isoformat()})


def _log_webhook_delivery(webhook_id, event, status_code, error=None):
    from app.models import ProjectAWebhookDelivery

    db.session.add(ProjectAWebhookDelivery(
        webhook_id=webhook_id,
        event=event,
        status_code=status_code,
        error=(error or "")[:500] if error else None,
    ))


def fire_webhooks(project_id, event, payload, webhook_id=None):
    if webhook_id:
        hooks = ProjectAWebhook.query.filter_by(id=webhook_id, project_id=project_id).all()
    else:
        hooks = ProjectAWebhook.query.filter_by(project_id=project_id, active=True).all()
    for h in hooks:
        try:
            events = json.loads(h.events_json or "[]")
        except (TypeError, ValueError):
            events = []
        if event not in events and not webhook_id:
            continue
        status_code = None
        err_msg = None
        try:
            import urllib.request
            import urllib.error

            data = json.dumps({"event": event, "payload": payload}).encode("utf-8")
            req = urllib.request.Request(
                h.url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                status_code = resp.getcode()
        except urllib.error.HTTPError as e:
            status_code = e.code
            err_msg = str(e.reason or e)
        except Exception as e:
            err_msg = str(e)
        _log_webhook_delivery(h.id, event, status_code, err_msg)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_member_role(project, user_id):
    if project.owner_id == user_id:
        return "admin"
    row = db.session.execute(
        text("SELECT role FROM project_membersa WHERE project_id = :pid AND user_id = :uid"),
        {"pid": project.id, "uid": user_id},
    ).fetchone()
    if row and row[0]:
        return row[0]
    if getattr(project, "project_type", None) == "public":
        return "contributor"
    return None


def custom_field_to_dict(cf):
    opts = None
    if cf.options_json:
        try:
            opts = json.loads(cf.options_json)
        except (TypeError, ValueError):
            opts = []
    return {
        "id": cf.id,
        "name": cf.name,
        "field_type": cf.field_type,
        "options": opts or [],
        "required_on_close": cf.required_on_close,
        "position": cf.position,
    }


def milestone_to_dict(m):
    return {
        "id": m.id,
        "title": m.title,
        "due_date": m.due_date.isoformat() if m.due_date else None,
        "color": m.color,
        "position": m.position,
        "task_ids": [t.id for t in (m.tasks or [])],
    }
