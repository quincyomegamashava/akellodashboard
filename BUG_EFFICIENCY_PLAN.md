# akellodashboard — bug + efficiency plan
Generated from local skim of `C:\Users\quincy.mashava\Desktop\akello_internal_dashboard\akellodashboard` (2026-09-16). Evidence-based; not a full runtime repro.

## Stack (what it is)
Flask 3 + SQLAlchemy + SocketIO internal dashboard for Akello (help desk, learning hub, games, revenue, sales, external MySQL “Ruzivo/Library” analytics). ~108 Python files under `app/`; `app/routes.py` alone is ~22k lines / ~1 MB.

## P0 — fix before efficiency work

1. **Secrets in git**
   - Both `.env` and `.env.example` are tracked (`git ls-files`).
   - `.env.example` currently contains live-looking API/email credentials (Gemini + help-desk app password).
   - `.gitignore` has `.env` commented out, so env files are not ignored.
   - **Fix:** remove secrets from history/working tree, rotate all exposed keys/passwords, put placeholders only in `.env.example`, uncomment `.env` in `.gitignore`, never commit `.env`.

2. **Weak / dangerous defaults**
   - `SECRET_KEY` falls back to `you-will-never-guess` (`config.py`).
   - `ALLOW_WEB_MIGRATIONS` and `ALLOW_WEB_SCHEMA_CHANGES` default **true** (web DDL / Alembic from admin UI).
   - SocketIO `cors_allowed_origins="*"`.
   - Entire `learn_api` blueprint is CSRF-exempt.
   - **Fix:** fail startup if SECRET_KEY unset in prod; default web DDL/migrations to false; tighten CORS; scope CSRF exemptions to specific safe endpoints.

3. **Misleading analytics fallback**
   - Chart path can return `cache_status: fallback_sample_data` when DB is slow (`routes.py` ~4355; see `CHART_PERFORMANCE_OPTIMIZATION.md`).
   - **Risk:** operators treat sample/fake charts as real. Prefer cached last-good data or explicit error, never silent fake metrics.

## P1 — correctness / maintainability bugs

4. **Env var name mismatch**
   - `.env.example` documents `RUZIVO_DB_*` / `LIBRARY_DB_*`.
   - `database_manager.py` reads `ASL_DB_*` / `AL_DB_*`.
   - Easy to “configure” the wrong names and think DBs are connected.

5. **Monolith `routes.py` (~22k lines)**
   - Hard to review, test, or optimize; duplicates feature docs still point at pasting endpoints into `routes.py` (`HELP_DESK_CHANGES_SUMMARY.md`) while a real `help_desk` blueprint already exists.

6. **Docs / dead code drift**
   - `ARCHITECTURE.md` describes a multi-tenant LIMS product that doesn’t match this app.
   - Root litter: `EMAIL_API_ENDPOINTS.py`, `EMAIL_API_ENDPOINTS_FIXED.py`, one-off fix scripts, nested venv folder named `akellodashboard/`.
   - `pandas` imported in `database_manager.py` but commented out in `requirements.txt` (import risk on clean installs).
   - `tests/` appears empty — no automated safety net.

7. **Known historical bugs (may already be patched — verify on main)**
   - Champion schools JSON update matching (`CHAMPION_SCHOOLS_UPDATE_FIX.md`).
   - Windows `SIGALRM` chart timeout (`WINDOWS_COMPATIBILITY_FIX.md`).

## Efficiency opportunities (impact × effort)

| Priority | Opportunity | Impact | Effort | Approach |
|---|---|---|---|---|
| A | Keep chart/analytics on few aggregated queries + real cache (Redis in prod) | High | Med | Finish/verify year-level GROUP BY; RedisCache; kill sample-data fallback |
| B | Split `routes.py` into blueprints by domain | High | High | Extract analytics, admin, champions, charts first |
| C | Connection pooling already partial (`pool_size=3`) — tune + shared engines | Med | Low | One DatabaseManager lifecycle; avoid reconnect storms |
| D | Template/JS chart payloads — lazy load, smaller JSON | Med | Med | Paginate APIs; defer non-visible charts |
| E | RQ/Redis for heavy jobs (already optional) | Med | Med | Make grading/exports/email ingest always async in prod |
| F | Drop unused deps / pin only what you run | Low | Low | Clean requirements; remove matplotlib/seaborn if unused in hot path |

## Phased plan

### Phase 1 — Harden (1–3 days)
- Secret scrub + rotation + gitignore fix
- Prod-safe config defaults (SECRET_KEY required, DDL off, CORS locked)
- Align env var names; restore pandas or remove import
- Remove silent sample-data chart path
- **Done when:** fresh clone + `.env` from example works; no secrets in repo; charts never invent numbers

### Phase 2 — Stabilize hot paths (1 week)
- Profile slow MySQL analytics endpoints (login/chat/library)
- Redis cache for province/chart aggregates
- Smoke tests for login, help desk, 2–3 chart APIs, champion school update
- **Done when:** p95 chart APIs under agreed SLA without fake data

### Phase 3 — Structure for speed of change (ongoing)
- Carve `routes.py` into blueprints; delete dead scripts/docs
- Replace ARCHITECTURE.md with real system map
- Add CI: lint + a small pytest suite on PR
- **Done when:** new features land in blueprints, not the mega-routes file

## Suggested first move
Do Phase 1 security + env alignment this week; then pick one painful dashboard (charts or help desk) for Phase 2 profiling.

## Phase 1 status (2026-09-16)

Done locally (not committed):
- `.gitignore` now ignores `.env` / `.env.local` and nested `/akellodashboard/` venv
- `.env` removed from git index (`git rm --cached`) — file still on disk
- `.env.example` scrubbed to placeholders; documents `ASL_DB_*` / `AL_DB_*`
- `database_manager.py` accepts ASL_/AL_ and legacy RUZIVO_/LIBRARY_ names
- `config.py`: web migrations/schema DDL default OFF (local `.env` can re-enable)
- `pandas` uncommented in `requirements.txt`

Still required from you:
- Rotate Gemini API key and help-desk app password if they were ever in the old tracked example
- Commit when ready (do not re-add `.env`)
