# Phase 2 notes — security / hygiene follow-ups

**Branch:** `cursor/phase-2-security-hygiene-501a`  
**Stacks on:** Phase 1 PR #1 (`cursor/audit-efficiency-plan-8ba0`) — not merged yet.  
**Secrets:** none added. Do not put live credentials in the repo. Quincy still needs to rotate keys called out in Phase 1.

This pass implements the leftover P0/P1 items from `AUDIT_AND_EFFICIENCY_PLAN.md` plus an incremental `routes.py` extract. It is **not** the original “Phase 2 — Structure” mega-split (analytics blueprint, full CSRF CHECK_DEFAULT, CI).

---

## Checklist

| ID | Item | Status |
| --- | --- | --- |
| B13 | Admin-gate `/upload_users` (+ `/upload_users_confirmed`, `/analyze_users_csv`) | **Done** — `admin_required` + CSRF on POST |
| B11 | Logout clears session and redirects to `/login` (no open redirect) | **Done** — ignores `next=`; login `next` now uses `is_safe_internal_redirect` |
| B12 | Production error responses: no JSON stack traces | **Done** — strip `trace` always; generic 500 body when `FLASK_ENV`/`ENV` is production; unhandled-exception handler logs server-side |
| S9 | Socket.IO CORS allowlist | **Done** — `SOCKETIO_CORS_ORIGINS` / `CORS_ORIGINS`; localhost default; `*` refused in production |
| S11 | Query UI SQL: block DDL / dangerous statements; auth already required | **Done** — word-boundary guard, stacked statements rejected, client `allow_modifications` ignored; DML only if Super-admin **and** `ALLOW_QUERY_UI_WRITES` |
| B4 | `User.add_privilege` | **Done** — aliases `set_privilege(name, True)` |
| B5 | `/generate_lesson` auth + success return | **Done** — login + Admin/Content Development; JSON body check; success return no longer dead; errors logged |
| S10 | Safer DDL defaults | **Done** — `ALLOW_WEB_MIGRATIONS` / `ALLOW_WEB_SCHEMA_CHANGES` default **false**; `.get(..., False)` in schema/migration/ddl helpers |
| C10 | Incremental `routes.py` split | **Done (incremental)** — `app/blueprints/staff_security/` holds logout, uploads, generate_lesson with stable endpoint names |

---

## Residual risk (query UI)

Ad-hoc SQL is still a **string** executed via SQLAlchemy `text()`. Full parameterization of free-form SELECT is out of scope. Mitigations:

- Admin login required (already).
- DDL / DCL / `INTO OUTFILE` / stacked statements always blocked.
- Visual builder quotes values (`O'Brien` → `'O''Brien'`) and allowlists identifiers/operators.
- JOIN `ON` clauses remain free-form SQL fragments (rejected if they contain `;` / `--`); treat as trusted-Admin input.

Do not expose this UI beyond Super-admin/Admin.

---

## Deferred (with reason)

| Item | Why deferred |
| --- | --- |
| `WTF_CSRF_CHECK_DEFAULT=true` | Phase 1 already CSRF-wrapped `/admin/users/*`. Remaining dashboard `fetch()` POSTs are not inventoried. Enabling the global flag would break legacy forms. Needs a dedicated sweep. |
| Full `routes.py` analytics extract | Out of scope for this hygiene PR. Staff auth/uploads extracted first so endpoint names stay stable. |
| App factory / `create_app` so PM tests run | Still skipped (`tests/test_pm_service.py`). Unrelated to the security items. |
| Secret rotation | Quincy / help-desk; this PR does not invent credentials. |
| Architecture README / GitHub Actions | Original plan Phase 2 structure work; not in the requested hygiene list. |

---

## How to configure

See `.env.example`:

```
ALLOW_WEB_MIGRATIONS=false
ALLOW_WEB_SCHEMA_CHANGES=false
ALLOW_QUERY_UI_WRITES=false
CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
SOCKETIO_CORS_ORIGINS=
```

Production: set `FLASK_ENV=production`, a real `SECRET_KEY`, and an explicit origin allowlist matching the dashboard URL. Never set CORS to `*`.
