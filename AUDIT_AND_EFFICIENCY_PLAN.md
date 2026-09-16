# Akello Dashboard — Audit and Efficiency Plan

**Date:** 2026-09-16  
**Scope:** Full repository review of `akellodashboard` (Flask dashboard + Learning Hub + mobile_app).  
**Method:** Static review of config, bootstrap, routes, database layer, analytics, auth, env files, tests, and requirements. Syntax check of `app/routes.py` (`python3 -m py_compile`). Runtime test suite was **not** executed in this agent environment (system Python has no Flask/pandas).  

**Secrets policy for this document:** live credentials were found in tracked files. Values are **not** repeated here. Rotate them; treat git history as compromised.

---

## Phase 1 implemented (this PR)

Code fixes on `cursor/audit-efficiency-plan-8ba0` after Quincy approved Phase 1. No `routes.py` split.

| Item | Status | What changed |
| --- | --- | --- |
| S1 Secrets untracked | Done earlier | `.env` / `.flaskenv` untracked; `.gitignore` ignores them. **Rotate anyway — history still has values.** |
| S2 Hardcoded MySQL in `routes.py` | Done | Pools and `get_direct_library_conn` / ruzivo fallback read `ASL_DB_*` / `AL_DB_*` only. Hardcoded `DB_CONFIG` removed. Root query scripts use the same env vars. |
| S3 Help-desk IMAP password fallback | Done | `_helpdesk_imap_settings()` — no literal app password. Missing config skips IMAP. |
| S4 PII export unauthenticated | Done | `/api/users-with-contact` and `/api/students-with-contact` require login + Admin. Excel engine is `openpyxl`. |
| S5 Debug leftovers | Done | Live `/check-columns` and `/api/testingdb1` routes removed. |
| S6 Public register → Admin | Done | Form no longer lists Admin/Manager. Server coerces those roles to `Brand Ambassador`. |
| S7 Weak SECRET_KEY | Done | `config.py` raises if `SECRET_KEY` is unset when `FLASK_ENV`/`ENV` is `production`/`prod`. Local fallback is `dev-only-insecure-secret-key` only. |
| S8 CSRF on staff mutations | Partial (intentional) | `WTF_CSRF_CHECK_DEFAULT` still false (legacy forms). `/admin/users/*` grant/revoke/patch/delete/reset/toggle now use `csrf_protect_unsafe`. `base.html` sends `X-CSRFToken` on mutating `fetch()`. Learning Hub unchanged. Exempt: public lead POST, `learn_api`. Full CHECK_DEFAULT=true remains Phase 2. |
| B1/B2 Fake chart data | Done | Random sample generators removed. Timeout returns last-good real cache or HTTP 408. |
| B3 HLF cache ignores dates | Done | Cache key is `hlf_weekly_stats_{start}_{end}`. |
| B8 pandas in requirements | Done | `pandas==2.3.2` uncommented. |
| B7 tests import `create_app` | Done (skip) | `tests/test_pm_service.py` skips unless `create_app` exists so collect does not explode. |
| `create_admin_user.py` default password | Done | Requires `ADMIN_BOOTSTRAP_PASSWORD`. |

**Not in this Phase 1 pass (follow-ups):** S9 Socket.IO CORS; S10 DDL defaults; S11 query-UI SQL; B4 `add_privilege` crash; B5 `/generate_lesson` dead return; B11 logout redirect; B12 stack traces in JSON; B13 `/upload_users` Admin gate; routes.py split.

---

## A. Executive summary

- **P0 — secrets in git.** Tracked `.env` and `.flaskenv` contain live database passwords, email app passwords, OpenAI/Gemini keys, Microsoft client secret, and related credentials. `.env.example` previously contained a real Gemini key and help-desk app password. `.gitignore` had `.env` **commented out**. This PR untracks `.env` / `.flaskenv` and sanitizes examples; **you must still rotate every exposed credential** because history retains them.
- **P0 — credentials hardcoded in application code.** `app/routes.py` embeds production MySQL hosts, users, and passwords for Ruzivo and Library connection pools (`get_ruzivo_pool`, `get_direct_library_conn`, `DB_CONFIG`). Help-desk IMAP falls back to a hardcoded app password when the env var is missing. Env files cannot save you while these literals remain.
- **P0 — unauthenticated data leaks.** `GET /api/users-with-contact` and `GET /api/students-with-contact` export PII (names, emails, mobiles) with **no** `login_required`. `GET /check-columns` dumps the library schema. `GET /api/testingdb1` is an unauthenticated debug query. `POST /generate_lesson` is unauthenticated (and its success return is dead code).
- **P0 — public self-registration as Admin.** `GET/POST /register` is public. `RegistrationForm.userRole` includes `Admin`. Combined with `SECRET_KEY` defaulting to `you-will-never-guess` (not set in `.env`) and `WTF_CSRF_CHECK_DEFAULT=false`, this is an account-takeover / privilege-escalation path.
- **P1 — analytics can show fake numbers.** `/api/platforms_overall_yearly` and `/api/hlf-weekly-stats/` return **random sample data** on timeout or DB error. Overview has a banner; HLF weekly sample payload also **breaks the frontend contract** (`week` vs `week_start` / `week_number`). `/api/hlf-weekly-stats/` cache key ignores `start_date`/`end_date`.
- **P1 — env contract is wrong.** Code reads `ASL_DB_*` / `AL_DB_*`. `.env.example` documented unused `RUZIVO_DB_*` / `LIBRARY_DB_*`. `.flaskenv` used `LIBRARY_DB_*`. Analytics pools ignore env entirely. Library DB name is inconsistent (`akello_library` vs `akello_library_2`).
- **P1 — tests and install are broken.** Only test file `tests/test_pm_service.py` imports `create_app`, which **does not exist**. `pandas` is imported throughout `app/routes.py` but **commented out** in `requirements.txt`. Excel export uses `engine="xlsxwriter"` which is not in requirements (`openpyxl` is).
- **P1 — CSRF off by default for staff POSTs.** Flask-WTF CSRFProtect is installed, but `WTF_CSRF_CHECK_DEFAULT` defaults to `false`. Learning Hub POSTs are guarded; most dashboard mutating APIs are not. Socket.IO allows `cors_allowed_origins="*"`.
- **Structure debt is the efficiency blocker.** `app/routes.py` is **25,155 lines / ~349 routes**. Newer features already live in blueprints; analytics, admin, and charts do not. Do **not** start a routes split until P0/P1 security and contract bugs above are fixed — otherwise the same bugs get copied into new modules.
- **What looks fine:** Flask-Login is applied to most staff HTML pages; Schema Studio is super-admin gated; the SQL query UI requires Admin; Learning Hub CSRF helper is coherent; public stakeholder lead form has honeypot + rate limit; login `next` is netloc-checked; `ALLOW_EXTERNAL_SCHEMA_CHANGES` defaults false; yearly platform queries were already collapsed from 36 per-month queries to 3 range queries.

---

## B. Bugs

Severity: **P0** = exploit / data leak / production credentials / broken auth. **P1** = crash, wrong analytics, failing tests, broken contract. **P2** = maintainability, defaults, stale docs, performance that is not user-facing-wrong.

### P0 — Security

| ID | Issue | Location | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| S1 | Live secrets tracked in git | `.env`, `.flaskenv` (this PR untracks them); previously `.env.example` | `git ls-files` listed `.env` and `.flaskenv`. Files contain DB passwords, `OPENAI_API_KEY`, `GEMINI_API_KEY`, email app passwords, Microsoft client secret. `.gitignore` had `# .env`. | Done in this PR: untrack files, ignore `.env`/`.flaskenv`, sanitize `.env.example`. **Still required:** rotate all exposed keys/passwords; consider `git filter-repo` / GitHub secret scanning; put secrets in a secret manager. |
| S2 | Production DB passwords hardcoded in Python | `app/routes.py` ~91–224, ~1459–1467 | `get_ruzivo_pool()` / `get_direct_library_conn()` / fallback `pymysql.connect` / `DB_CONFIG` use literal host, user, password, database. | Replace with `ASL_DB_*` / `AL_DB_*` (same names as `database_manager.py`). Fail closed if unset. Never log passwords. |
| S3 | Help-desk IMAP password fallback | `app/routes.py` ~19053–19054, 19109, 19347–19348, 19925–19926, 20354–20355 | `os.getenv('HELP_DESK_EMAIL_APP_PASSWORD') or '<literal>'` | Remove the literal. If unset, skip IMAP and log a config error. |
| S4 | Unauthenticated PII export | `app/routes.py` `users_with_contact` ~6445, `students_with_contact` ~6500 | No `@login_required`. Queries `users` / `tblstudents` for email and mobile; returns `.xlsx`. | Add `@login_required` plus Admin (or a dedicated privilege). Prefer streaming via `openpyxl`. |
| S5 | Unauthenticated schema / debug APIs | `app/routes.py` `/check-columns` ~10043, `/api/testingdb1` ~6636, `POST /generate_lesson` ~312 | No login. `check-columns` runs `SHOW TABLES` + `DESCRIBE`. `testingdb1` runs a live analytics query. | Delete or gate behind Admin. See also B7 (testingdb1 crash). |
| S6 | Public registration can create Admin | `app/routes.py` `/register` ~17400; `app/forms.py` `RegistrationForm.userRole` includes `('Admin', 'Admin')` | Endpoint is public. Form choices include Admin. | Disable public `/register` or restrict to invite-only. Drop Admin from the form. Create admins only in `/administration`. |
| S7 | Weak / missing Flask `SECRET_KEY` | `config.py` L17; `.env` has no `SECRET_KEY` | Default `'you-will-never-guess'`. Sessions and CSRF tokens are forgeable if this ships. | Require `SECRET_KEY` at startup in non-debug. Generate with `secrets.token_hex(32)`. |
| S8 | CSRF not enforced on most POSTs | `config.py` L22–24; `app/__init__.py` L17, L112; `docs/LEARNING_HUB.md` | `WTF_CSRF_CHECK_DEFAULT` defaults **false**. `csrf.exempt(learn_api_bp)`. Learning Hub uses `require_csrf_on_post()`; staff JSON APIs (admin user grant/revoke, branding, collateral, PM, etc.) do not. | Keep Learning Hub guards. Plan a sweep: add CSRF tokens to dashboard JS (pattern already in `help_desk.js` / `akello_revenue.js`) then set `WTF_CSRF_CHECK_DEFAULT=true`. Exempt only token-authenticated APIs. |
| S9 | Socket.IO CORS allow-all | `app/__init__.py` L22 | `socketio = SocketIO(app, cors_allowed_origins="*")` | Restrict to the dashboard origin(s). |
| S10 | Dangerous defaults for web DDL / debug | `config.py` L95–98; `.flaskenv` had `FLASK_DEBUG=1` | `ALLOW_WEB_MIGRATIONS` and `ALLOW_WEB_SCHEMA_CHANGES` default **true**. Debug was on in tracked flaskenv. | Default both flags to **false**. Never commit `FLASK_DEBUG=1`. Schema Studio already requires Super-admin (good). |
| S11 | SQL query UI can run writes; keyword filter is bypassable / false-positive | `app/database_routes.py` ~104–136; `database_manager.execute_query` interpolates SQL | Dangerous-keyword check is substring (`CREATE` matches `created_at`). `allow_modifications` is a client JSON flag. Visual builder interpolates values into SQL (`'{value}'`). | Allow SELECT-only unless Super-admin + server-side flag. Use parameterized queries. Parse with sqlparse / allowlist instead of substring. |

### P1 — Correctness / crashes / contracts

| ID | Issue | Location | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| B1 | Chart APIs return **random fake data** on timeout/error | `app/routes.py` `_get_sample_chart_data` ~4515, `_get_sample_weekly_data` ~4783; used by `/api/platforms_overall_yearly` and `/api/hlf-weekly-stats/` | `random.randint` monthly/weekly series; `_sample_data: True`. Cached **only** if not sample (yearly). Overview banner exists (`overview.html` ~1049). | Stop returning 200 with invented metrics. Return 504/408 with `{error, timeout: true}` and empty series, or last **real** cache. Keep the banner only if you keep a clearly labeled demo mode behind a flag. |
| B2 | HLF weekly sample payload ≠ live payload | `_get_sample_weekly_data` vs `_hlf_weekly_stats_impl`; `app/templates/HLFStats.html` ~545, 605, 661 | Live weeks: `week_start`, `week_number`. Sample weeks: `week` only. UI uses `week.week_number` / `week.week_start` → `Week undefined` / blank dates. | Delete sample fallback, or match the live schema. |
| B3 | HLF weekly cache ignores date range | `@cache.cached(..., key_prefix='hlf_weekly_stats')` on `/api/hlf-weekly-stats/` ~4586 | Static key. First request’s `start_date`/`end_date` is served for 6 hours regardless of later params. | Include dates in the cache key (same pattern as `_json_ok_list_response` public caches at ~25122). |
| B4 | `User.add_privilege` does not exist | `grant_privilege` ~804–816; `app/models.py` User | Route calls `user.add_privilege(privilege)`. Model has `set_privilege` / `remove_privilege` / `has_privilege` only. | Call `user.set_privilege(privilege, True)` or add `add_privilege`. Add a unit test. |
| B5 | Lesson generation never returns success | `/generate_lesson` ~443–447 | After `if not content: return 502`, the `return jsonify({"lesson": content})` is **indented inside** that `if`. Successful generation falls off the function (`None` → 500). Also `data.get` will crash if body is not JSON. | Dedent the success return. Null-check `request.get_json()`. Add `@login_required`. |
| B6 | `/api/testingdb1` SQL placeholders with no params | ~6642–6654 | Query uses `BETWEEN %s AND %s` then `cursor.execute(query)` with **no arguments**. | Delete the route (debug leftover) or pass dates. |
| B7 | Tests import missing factory | `tests/test_pm_service.py` L6–28 vs `app/__init__.py` | `from app import create_app` — no `create_app` in the package (only a module-level `app = Flask(__name__)`). | Introduce `create_app(config)` (factory) **or** change tests to use `app.app`. Tests also construct `User(..., password='x')` but User has `password_hash`, and `firstname`/`lastname`/`userRole` are required — tests would still fail. |
| B8 | `pandas` required at import but commented out of requirements | `requirements.txt` L59 `# pandas==2.3.2`; `app/routes.py` L34, L49, and later re-imports | Importing `app.routes` (which `__init__.py` always imports) needs pandas. Fresh `pip install -r requirements.txt` cannot start the app. | Uncomment pandas (pin a version). Same for any other commented runtime deps actually imported. |
| B9 | Excel engine `xlsxwriter` not in requirements | `app/routes.py` ~6470, 6532 | `pd.ExcelWriter(..., engine="xlsxwriter")`. Requirements list `openpyxl` only. | Use `engine="openpyxl"` (already used at ~16327) or add `xlsxwriter`. |
| B10 | Env var name mismatches | `.env.example` (old), `.flaskenv` (old), `database_manager.py`, `routes.py`, Microsoft OAuth ~18861 | Manager: `ASL_DB_*`, `AL_DB_*`. Example used `RUZIVO_DB_*` / `LIBRARY_DB_*`. Flaskenv used `LIBRARY_DB_*`. `.env` used invalid `application_client_id = ...` (spaces; not exported). Code expects `MICROSOFT_CLIENT_ID`. `content_dev/routes.py` reads `OLLAMA_MAX_TOKENS`; config documents `OLLAMA_NUM_PREDICT`. Library name: hardcoded `akello_library` vs `.env` `akello_library_2` vs HTML “akello_library_2”. | Single documented contract (this PR’s `.env.example`). Make `routes.py` pools read the same vars. Pick one library database name. |
| B11 | `logout` redirects to a login-required page | `logout` → `url_for('welcome')`; `welcome` is `@login_required` | After logout, Flask-Login bounces to `/login`. Works, but is a broken intended landing. | Redirect to `/login`. |
| B12 | Stack traces in JSON | `app/routes.py` ~9302 `asl_total_sec_content` | `return jsonify({"error": str(e), "trace": traceback.format_exc()})` | Log server-side; return a generic 500 to the client. |
| B13 | `upload_users` not Admin-gated | `/upload_users` ~634 vs `/upload_users_confirmed` ~554 | Confirmed path checks `userRole != 'Admin'`. Legacy `/upload_users` is only `@login_required` and can create arbitrary roles. | Require Admin (and CSRF). Prefer deleting the legacy path. |

### P2 — Smaller / structural

| ID | Issue | Location | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| C1 | `ARCHITECTURE.md` describes a multi-tenant LIMS, not this product | repo root | Tenant isolation, FDA 21 CFR, sample analysis modules — none of that is in `app/`. | Replace with an accurate system map (dashboard, Ruzivo, Library, Learning Hub, PM, help desk). |
| C2 | No root README, no CI | repo | No `.github/workflows`, no Dockerfile, no `pytest.ini`. | Add README (run, env, tests) and a minimal CI job: `pip install -r requirements.txt && pytest`. |
| C3 | Jupyter share tree committed | `akellodashboard/` (~8MB, 42 files) | Looks like a local JupyterLab/plotly install, not application code. | Remove from git unless Quincy confirms it is needed. |
| C4 | Duplicate / dead files | `EMAIL_API_ENDPOINTS.py`, `EMAIL_API_ENDPOINTS_FIXED.py`, `mobile_help_desk_endpoint.py`, `monitoring_dashboard_broken.html`, `bash.exe.stackdump` | Docs tell you to copy endpoints into `routes.py`; copies already live there. | Archive or delete after confirming unused. |
| C5 | Mutable JSON default on User.privileges | `app/models.py` L80 | `mapped_column(sa.JSON, default={})` shares one dict at class level. | `default=dict` or `default=lambda: {}`. |
| C6 | `before_request` writes DB on every authenticated request | `app/routes.py` ~271–275 | Updates `last_seen` and `db.session.commit()` always. ActivityTracker also hooks before/after request. | Throttle last_seen (e.g. if older than 60s). |
| C7 | `get_tables` runs `COUNT(*)` per table | `database_manager.py` ~223–256 | Up to 50 tables; `COUNT(*) ... LIMIT 1` does **not** limit the count in MySQL. | Use `information_schema.TABLE_ROWS` (Schema Studio already has an exact/approx split). |
| C8 | YEARWEEK vs labeled week_start | `_hlf_weekly_stats_impl` ~4724–4727 | `week_start = start_date + timedelta(weeks=i)` then `%G%V`. If `start_date` is not Monday, labels are not ISO week starts even though keys are ISO week numbers. | Normalize `start_date` to Monday; document the week definition. |
| C9 | Local Python sandbox is not isolation | `app/learning_hub/services/sandbox.py` | Docstring already warns: subprocess, not a jail. | Require Judge0/Docker in production; keep local runner for dev only. |
| C10 | Duplicate imports / unused deps in `routes.py` | top of file | `pandas`, `seaborn`, `uuid`, `os` imported twice; `from psycopg2 import sql` unused if app DB is SQLite; `asyncio`/`aiomysql` unused in the sync chart paths reviewed. | Clean during the routes split (Phase 2), not as a drive-by. |
| C11 | Logging always DEBUG | `app/logging_config.py` | File + console handlers at DEBUG, including Werkzeug. | INFO in production; DEBUG when `FLASK_DEBUG`. |
| C12 | Help-desk legacy page unauthenticated | `/helpdesk` ~17343 | Renders `help_desk.html` with no login. The real hub is `/help-desk/` (blueprint, login required). | Redirect `/helpdesk` → `/help-desk/` or add login. |

**Hypothesis (not confirmed without a live DB):** several analytics endpoints still wrap queries in `YEAR(col) = %s` or `DATE(col) BETWEEN`, which prevents index use. `CHART_PERFORMANCE_OPTIMIZATION.md` says yearly platforms moved to range predicates; other endpoints may not have. Treat as a Phase 2 measurement task, not a filed bug.

**Not bugs (looked fine):**

- Schema Studio routes use `@super_admin_required`; external DDL defaults off.
- Database query UI requires Admin + login.
- Learning Hub learner/guardian/admin POSTs call `require_csrf_on_post()`.
- Public sales lead POST is CSRF-exempt **by design** (public form) and has honeypot + rate limit + consent.
- Login `next` rejects external netlocs.
- `province_stats_service.py` is a clean extraction with cache keys and a province allowlist.
- Game public self-registration is explicitly disabled (`register_game_user_public` returns 403).

---

## C. Required fixes before (or alongside) efficiency work

Do these **before** splitting `routes.py` or adding Redis/caching layers. Otherwise you duplicate secrets, fake charts, and unauthenticated routes into new modules.

1. **Rotate every secret that was in git** (DB users, email app passwords, OpenAI, Gemini, Microsoft client secret, Google app password). Assume they are public. Recreate DB users rather than only changing passwords if those accounts are shared.
2. **Stop hardcoding credentials in `app/routes.py`.** Connection pools must read `ASL_DB_*` / `AL_DB_*`. Remove help-desk password literals.
3. **Lock down anonymous endpoints:** `/api/users-with-contact`, `/api/students-with-contact`, `/check-columns`, `/api/testingdb1`, `/generate_lesson`, `/register` (Admin choice), `/helpdesk`.
4. **Set a real `SECRET_KEY`** and fail startup if missing in production.
5. **Turn off fake chart fallbacks** (or gate behind `ALLOW_SAMPLE_CHARTS=false` default). Fix HLF cache keys.
6. **Uncomment/pin pandas** (and fix xlsxwriter vs openpyxl) so a clean install boots.
7. **Fix `grant_privilege` / `add_privilege`** and `/generate_lesson` success return (small, localized).
8. **Do not enable `WTF_CSRF_CHECK_DEFAULT=true` until** dashboard JS sends tokens; ship that as a dedicated change with a checklist of POST routes.
9. **Default `ALLOW_WEB_MIGRATIONS` / `ALLOW_WEB_SCHEMA_CHANGES` to false.**
10. **Repair tests:** app factory or rewrite `tests/test_pm_service.py` so `pytest` can run in CI.

This PR only does item-adjacent hygiene for (1): untrack env files, ignore them, sanitize examples. Code still contains hardcoded DB passwords until a follow-up.

---

## D. Efficiency opportunities (ranked)

Impact × effort. Do not start these until Section C items 1–7 are in motion.

| Rank | Opportunity | Impact | Effort | Approach |
| --- | --- | --- | --- | --- |
| 1 | **Stop returning sample data; fail fast + serve last good cache** | High (trust + fewer 20s thread timeouts) | S | Remove `_get_sample_*`. On timeout return last non-sample cache or 408. Frontend already has retry UI. |
| 2 | **Fix HLF cache key; cache by date range** | High (wrong charts) | S | `key_prefix=lambda: f"hlf_weekly:{start}:{end}"`. |
| 3 | **Throttle `last_seen` + activity tracker writes** | Med–High (write amplification on every request) | S | Update last_seen if stale; skip logging for `/api/monitoring/heartbeat` and static. |
| 4 | **One connection helper, env-driven pools** | High (ops + security + fewer leaked connections) | M | Delete hardcoded pools; reuse `DatabaseManager` or a thin `get_mysql(db_key)` with pool_size, pre_ping, contextmanager. `province_stats_service` already imports from `routes` — invert that. |
| 5 | **Index-friendly analytics SQL** | High on overview/province pages | M | Audit remaining `YEAR()` / `DATE(col)` predicates; use `[start, end)` ranges; confirm indexes on `tblstudents_login.login_date`, `logins.created_at`, `tblask_akello_chat_logs.created_at`. Measure with `EXPLAIN`. |
| 6 | **Split `app/routes.py` by domain** | High (maintainability); no user-visible perf until queries move | L | See Phase 2. Extract charts → `app/blueprints/analytics/`. Do **not** move 25k lines in one PR. |
| 7 | **Redis cache in production** | Med (multi-worker FileSystemCache is OK on one host; Redis helps multi-instance) | M | `CACHE_TYPE=RedisCache` already documented in `config.py`. Only after keys are correct (else Redis caches wrong HLF data). |
| 8 | **Schema listing without COUNT(*)** | Med for Database Studio | S | Approximate row counts. |
| 9 | **Drop committed Jupyter tree / unused scripts** | Low–Med clone size | S | Delete `akellodashboard/` if unused. |
| 10 | **Frontend chart waterfalls** | Med | M | Overview already sequential-ish; after APIs are honest, prefetch with HTTP cache headers. |
| 11 | **Learning Hub job queue** | Med when grading is on | M | Redis/RQ already optional (`rq_worker_learn.py`). Document when to run the worker. |
| 12 | **Mobile app** | Unknown | — | Flutter project is a stub README. Out of scope until API contracts for `/api/mobile/*` are documented (`docs/pm-api.md` exists for PM). |

---

## E. Phased plan

### Phase 1 — Safety and truth (do first)

**Work**

- Rotate secrets; finish removing hardcoded passwords from `routes.py`.
- Auth-gate or delete anonymous PII/debug routes; close public Admin registration.
- Require `SECRET_KEY`; `FLASK_DEBUG=0` in any shared env.
- Remove sample-data fallbacks; fix HLF cache key and sample schema mismatch.
- Pin pandas; fix Excel engine; fix `add_privilege`; fix `generate_lesson` return.
- Make tests importable (`create_app` or rewrite tests).

**Success criteria**

- `git ls-files` does not include `.env` or `.flaskenv`.
- `rg` for production passwords / `sk-proj-` / `AIza` in tracked files is empty (except this report saying “do not commit them”).
- Unauthenticated `curl` to `/api/users-with-contact` and `/api/students-with-contact` returns 401/302.
- `/register` cannot create `userRole=Admin`.
- `/api/platforms_overall_yearly` never sets `_sample_data`.
- `pip install -r requirements.txt` then `python -c "from app import app"` succeeds (needs DB optional/lazy — today pools are lazy, pandas is not).
- `pytest tests/` collects and passes on SQLite.

### Phase 2 — Structure (after Phase 1)

**Work**

- Extract analytics/chart routes from `app/routes.py` into `app/blueprints/analytics/` (start with platforms yearly, HLF weekly, province stats — `province_stats_service.py` is the template).
- Extract connection helpers to `app/db_external.py`.
- Add CSRF tokens to remaining dashboard fetch() POSTs; then enable `WTF_CSRF_CHECK_DEFAULT`.
- Add GitHub Actions: install, pytest, a secrets scan (`gitleaks` or `trufflehog`).
- Replace `ARCHITECTURE.md` with a real map; add root README.

**Success criteria**

- `app/routes.py` no longer contains MySQL analytics SQL (or is under ~5k lines and still shrinking).
- New chart endpoints live behind one blueprint with shared cache helpers.
- CI red if tests fail or if `.env` is added back.
- Staff POST without CSRF token is rejected.

### Phase 3 — Performance (after measurement)

**Work**

- `EXPLAIN` the remaining slow queries; add indexes on the MySQL side (Ruzivo/Library are external — coordinate with DB owners).
- Prewarm MTD province stats (helpers already exist in `province_stats_service.py`).
- Redis cache for multi-worker deploys.
- Judge0 for Learning Hub sandbox in production.
- Restrict Socket.IO CORS; consider splitting realtime from the gunicorn/werkzeug web process.

**Success criteria**

- Overview yearly charts: p95 **live** payload &lt; 3s when cache warm, &lt; 15s cold, **never** random data.
- No `COUNT(*)` on every table in the query UI.
- Documented production config: `SECRET_KEY`, Redis, `ALLOW_WEB_SCHEMA_CHANGES=false`, `FLASK_DEBUG=0`.

---

## Appendix: repo map (as it actually is)

| Path | Role |
| --- | --- |
| `app.py` | Flask shell context; not the WSGI factory |
| `app/__init__.py` | Instantiates global `app`, CSRF, login, SocketIO, registers blueprints, seeds STEM games, starts scheduler |
| `app/routes.py` | ~25k lines: auth, admin, analytics, charts, champions, branding, games, email helpdesk leftovers, public SM proxies |
| `app/database_manager.py` | Env-based MySQL engines for the admin query UI |
| `app/database_routes.py` | `/databases` query tool (Admin) |
| `app/blueprints/*` | Newer domains: help desk, meeting notes, sales, revenue, learning hub, content dev |
| `config.py` | Flask config; loads repo-root `.env` |
| `tests/` | One PM unit test file (currently un-runnable as written) |
| `mobile_app/` | Flutter stub |
| `akellodashboard/` | Committed JupyterLab share tree (likely accidental) |

**This environment:** system Python 3 had neither Flask nor pandas, so pytest was not executed here. `python3 -m py_compile app/routes.py` succeeded (syntax OK).

---

## Appendix: this PR’s code/doc changes (intentionally small)

- Untrack `.env` and `.flaskenv` (files remain on disk locally if present).
- Ignore `.env`, `.flaskenv`, `.env.*.local`.
- Replace `.env.example` with placeholder values and the **actual** variable names the code reads.
- Add `.flaskenv.example` with `FLASK_APP` only.
- Add this plan.
