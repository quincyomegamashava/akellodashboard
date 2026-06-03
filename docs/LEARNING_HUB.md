# Akello Learning Hub

Separate **learner** site (`/learn`), **guardian** portal (`/learn/guardian`), **staff** tools (`/learn/admin`), and **JSON API** (`/api/v1/learn`).

## Product

- **Structured tracks, quizzes, challenges, and XP** — aimed at primary through tertiary learners.
- **Explorer curriculum** (seed from admin): one published quiz-style challenge per curriculum category (Python, JavaScript, Web Development, AI, Robotics, Scratch, Cybersecurity, Data Science, ICT Fundamentals, Computer Literacy), plus a Python **coding** warmup on the shared “Akello Explorer Path” track.
- **Skill level** (`beginner` / `intermediate` / `advanced`) is **recomputed from recent graded attempts** (quizzes + coding) — see `app/learning_hub/services/skill_level.py`.
- **Guardian linking**: learner dashboard → “Generate pairing code”; guardian portal → enter learner **username** + **code** (30-minute expiry).
- **Track progress**: `LearnLearnerTrackProgress.percent_complete` is recomputed as **(challenges passed in that track) / (challenges linked to the track)** via `app/learning_hub/services/track_progress.py` when you finish a quiz/coding attempt and when the dashboard loads. Each track only counts its own `LearnTrackChallenge` rows — e.g. **ICT Fundamentals Track** stays at 0% until you pass challenges that belong to that track, not only Explorer Path activities.

## XP and retries

- **First passing attempt only**: XP and streak bumps apply only when the learner **passes** a challenge **and** they have **no earlier graded passing attempt** for that same challenge (`app/learning_hub/services/attempt_xp_policy.py`). Later passes are still graded and stored (`score`, `passed`, etc.) but **`xp_awarded`** is `0`.
- Quiz UI and coding grading flash messages distinguish earning XP vs practice-only retries.

## Staff Learn Admin URLs

Requires **Admin** or **Learning Hub Admin** privilege.

| Path | Purpose |
|------|---------|
| `/learn/admin/` | Overview metrics, per-category XP mini-leaderboards, seed actions |
| `/learn/admin/learners` | Paginated learner directory |
| `/learn/admin/learners/<id>` | Learner profile + attempt history |
| `/learn/admin/challenges` | Challenge catalog + attempt/pass counts |
| `/learn/admin/challenges/<id>` | Challenge detail + recent attempts |
| `/learn/admin/challenges/new` | Stub create challenge form |

## Security

- **CSRF**: `WTF_CSRF_CHECK_DEFAULT` defaults to **false** so legacy staff dashboard POST routes are unchanged. **Learner, guardian, and Learn Admin** blueprints validate POSTs with `validate_csrf(token)` via `require_csrf_on_post()` (`app/learning_hub/csrf_post_guard.py`), matching Flask-WTF 1.2.x. Forms include hidden `csrf_token`; headers `X-CSRFToken` / `X-CSRF-Token` are also accepted.
- **`learn_api` blueprint** is **`csrf.exempt`** for JSON clients. Treat `POST /api/v1/learn/coding-submit` as **session-authenticated / same-origin** until you add API tokens or CSRF header support.
- **Coding sandbox**: local Python runner is a **development convenience** only. Use **Judge0** (`JUDGE0_*` in `config.py`) and/or isolated workers in production.
- **Coding UX**: challenges with `challenge_type="coding"` use a **CodeMirror** editor, **Run sample** (`POST /learn/challenges/<id>/run-sample`) to execute only `public_tests` (or the first test in `tests` if `public_tests` is omitted), and **Submit all tests** for graded attempts with XP. Optional `public_tests` in `content_json` keeps part of the suite private until final submit (see seed `PYTHON_CODING`).

## Async grading (RQ + Redis)

- Optional **`REDIS_URL`**: coding jobs enqueue to RQ queue **`learn_hub`**; if Redis is unavailable, grading runs **synchronously** in the web process (`app/learning_hub/queue.py`).
- Worker entrypoint: [`rq_worker_learn.py`](../rq_worker_learn.py) (or `rq worker learn_hub --url <REDIS_URL>`).

## Object storage

- Learner uploads use `app/learning_hub/storage.py`: **local** `instance/learn_uploads/` by default; **S3-compatible** when `LEARN_S3_BUCKET` / `AWS_*` / `AWS_ENDPOINT_URL` are set.

## PWA

- Manifest: `app/static/learn/site.webmanifest`
- Service worker: `app/static/learn/sw.js`, registered from `learn/base.html` at **`/learn/sw.js`** (`learn_portal.learn_service_worker`).

## Database

Models: [`app/learning_hub/models/`](../app/learning_hub/models/).

Run migrations (resolve multiple heads if Alembic reports them):

```bash
flask db upgrade
```

Pairing columns on learners: migration `m3n4o5p6q7r8_learn_learner_pairing_columns.py` (after initial Learning Hub revision).

## Operations checklist

1. **Admin** (or **Learning Hub Admin** privilege): **Learn Admin** → **Seed Explorer curriculum** (or **Seed demo** for the smaller demo track).
2. Open **Akello Learn** → register learner → enroll in **Akello Explorer Path** → complete category quizzes and the Python coding challenge.
3. Optional: start **RQ worker** with `REDIS_URL` set for async coding grades.
4. Guardians: **Guardians** in the learn nav → register → **Link learner** with pairing code.

## Config reference (env)

| Variable | Purpose |
|----------|---------|
| `REDIS_URL` | RQ broker; omit for sync grading |
| `JUDGE0_API_URL`, `JUDGE0_API_TOKEN`, `JUDGE0_LANGUAGE_PYTHON_ID` | Remote Python runs |
| `LEARN_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL` | S3 uploads |
| `WTF_CSRF_ENABLED`, `WTF_CSRF_CHECK_DEFAULT` | CSRF toggles |
