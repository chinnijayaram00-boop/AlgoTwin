# ALgotwin

ALgotwin is a production-oriented foundation for an AI-powered DSA learning, visualization, and interview platform. The repository provides a runnable web shell, a FastAPI REST API, persistent user accounts with bearer-token authentication, a seeded DSA catalog, an out-of-process code runner that grades a learner's program against a problem's visible cases, database-ready models, environment configuration, and the boundaries needed for future judged submissions, AI explanations, algorithm visualization, and interview features.

## Stack

- Frontend: React, Vite, React Router, Monaco Editor, Recharts, ESLint, Vitest
- Backend: FastAPI, Pydantic Settings, SQLAlchemy 2, PyJWT, pwdlib (Argon2)
- Database: SQLite locally, PostgreSQL through `DATABASE_URL`
- Migrations: Alembic, with a non-destructive initial baseline revision

## Repository layout

```text
frontend/
  src/app/                 routing and app configuration
  src/components/          reusable UI and layout components
  src/features/             auth, dashboard, and problem feature modules
  src/hooks/                reusable data hooks
  src/pages/                route-level screens
  src/services/             API client and service adapters
  src/styles/               design tokens and global styles
  src/test/                 frontend test setup and tests
backend/
  app/api/                  REST routers and route modules
  app/core/                 configuration, security, and application concerns
  app/db/                   SQLAlchemy engine, sessions, and schema compatibility
  app/schemas/              request and response contracts
  app/services/             application use cases
  app/judge/                out-of-process code execution and grading
  app/algorithms/           algorithm execution contracts and registry
  app/visualization/        visualization data contracts
  app/ai/                   AI provider boundary and configuration
  tests/                    backend tests
database/
  models/                   SQLAlchemy domain models
  problem_defs/             the seeded problem catalog, as validated definitions
  problem_catalog.py        catalog synchronization used by the seed
  problem_spec.py           catalog shape and the offline judge oracle
  migrations/               Alembic migration environment
```

## Prerequisites

- Node.js 20 or newer
- npm 10 or newer
- Python 3.12 or newer
- PostgreSQL only when using the PostgreSQL URL; SQLite is the local default

## Local setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
npm install
copy .env.example .env
copy frontend\.env.example frontend\.env
```

Generate a signing secret for `.env` before starting the API:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the printed value as `JWT_SECRET_KEY` in `.env`. The API refuses to start without it because registration and login cannot issue safe access tokens.

On macOS or Linux, activate the environment with `source .venv/bin/activate` and use `cp` instead of `copy`.

## Run the applications

Start the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001
```

Start the frontend in another terminal:

```powershell
npm run dev:frontend
```

Open `http://localhost:5174`. The API root is `http://localhost:8001`; health and readiness endpoints are under `http://localhost:8001/api/v1/health` and `http://localhost:8001/api/v1/health/ready`.

Run both from the repository root. The API resolves `.env` relative to the repository, so the CORS allowlist and `JWT_SECRET_KEY` load the same way from any working directory.

The first visit redirects to `/login`. Create an account at `/register`; the issued token is stored in browser `localStorage` and restored on later visits, so the workspace survives reloads and restarts.

## Verification commands

```powershell
npm run lint:frontend
npm run typecheck:frontend
npm run test:frontend
npm run build:frontend
.\.venv\Scripts\python.exe -m ruff check backend database
.\.venv\Scripts\python.exe -m pytest
```

`typecheck:frontend` runs TypeScript in JavaScript-check mode; it is intentionally configured so the JavaScript UI remains lightweight while still exposing a repeatable type validation command.

Verified on the current `main`:

| Command | Result |
| --- | --- |
| `python -m pytest` | 683 passed |
| `python -m ruff check backend database` | All checks passed |
| `npm run lint:frontend` | 0 errors (2 pre-existing warnings) |
| `npm run typecheck:frontend` | clean |
| `npm run test:frontend` | 233 passed (13 files) |
| `npm run build:frontend` | succeeds, with the chunk-size warning noted below |
| `git diff --check` | clean |

`test_judge.py` is the slowest file (223 tests) because it actually executes code in every language the catalog advertises.

## Database configuration

The default local URL is `sqlite:///./algotwin.db`. For PostgreSQL, set a URL such as:

```text
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/algotwin
```

`AUTO_CREATE_TABLES=true` is convenient for local development. For deployed environments, set it to `false` and use Alembic:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

The Alembic configuration expects the project root as its working directory and reads `DATABASE_URL` from `.env`. The baseline revision `533005ea0596` creates the full schema and is safe to apply to a database that already exists: tables and indexes are created with `if_not_exists`, a pre-existing `users` table gains `name`, `password_hash`, `created_at`, and `updated_at` without dropping rows, and a legacy `display_name` column is carried over rather than discarded. `downgrade` is intentionally inert so reversing it cannot destroy learner data. Generate follow-up revisions with:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe the change"
```

Do not commit `.env`, database files, or AI keys.

### Seeded problem catalog

`database/problem_defs/` holds 50 judge-ready problems (10 Easy, 27 Medium, 13 Hard) as validated Python definitions — statement, input and output format, hints, tags, per-problem limits, visible and hidden cases, and a reference solution per language. The bank carries 399 cases (197 visible, 202 hidden), 6 to 10 per problem with an average of 8, spread over 12 primary topics and 44 distinct topics in all; every problem has exactly 5 hints, a 256 MB memory limit, and a time limit of 2000 to 5000 ms. `SEED_PROBLEM_CATALOG=true` (the default) validates each definition and then upserts it on startup.

Language coverage is Python and JavaScript for all 50 problems and Java for the 36 that ship a Java reference solution — 136 problem/language pairs in total.

Validation is not a formality: `database/problem_spec.py` runs every reference solution against the definition's own cases before the row is written, so a definition whose reference solution does not pass fails the seed rather than shipping a problem the judge would mark wrong. Language support is checked against the judge registry for the same reason — a definition may only advertise a language the runner can execute, because a tab that ends in a `422` is a defect. The catalog's advertised set is exactly the registry's: `python`, `javascript`, `java`.

Synchronization is non-destructive. A definition is matched by slug, and an existing row keeps its id, its attachment text, and its `is_published` flag; only judge-owned columns are refreshed. Changing a problem's cases changes its row, so treat an edited definition as a schema change for anything already graded against the old cases.

## Authentication

`POST /api/v1/auth/register` and `POST /api/v1/auth/login` return a short-lived bearer token plus the public profile; `GET /api/v1/auth/me` resolves the profile from that token and `POST /api/v1/auth/logout` returns `204`.

Backend:

- Passwords are hashed with Argon2id through `pwdlib` with a per-hash salt. Plaintext is never persisted, logged, or returned, and a missing or corrupt stored hash fails the login with `401` rather than a `500`.
- `UserProfile` is an explicit projection (`id`, `name`, `email`, `created_at`, `updated_at`). `password_hash` is absent from every response schema, and the test suite fails if it ever appears in the published OpenAPI contract.
- Tokens are JWTs signed with `JWT_SECRET_KEY` using `JWT_ALGORITHM`, valid for `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`. The payload carries only `sub`, `iat`, `exp`, `type`, and a unique `jti` — no email or name, so a leaked token discloses no personal data. Signature, algorithm, expiry, and token type are all verified, and a token naming a user that no longer exists is rejected.
- Emails are normalized to lowercase on write and compared case-insensitively, so `Ada@example.com` and `ada@example.com` are the same account. A duplicate returns `409` whether it is caught by the pre-check or by the unique index.
- `get_current_user` in `backend/app/api/dependencies.py` is the reusable guard. Apply it to every user-specific route. `health` and `health/ready` stay public.
- `AUTO_CREATE_TABLES=true` and startup also apply an idempotent `users` compatibility upgrade: a legacy table with `display_name` is rebuilt into `name`, `email`, `password_hash`, `created_at`, `updated_at` while preserving existing rows, IDs, and dependent `progress` rows. Legacy rows keep a null `password_hash` and cannot sign in until a password is set.
- Without a usable `JWT_SECRET_KEY` the auth routes return `503` rather than issuing or trusting anything.

Frontend:

- `AuthProvider` owns the session. The token lives in `localStorage` under `algotwin.auth.token`; on start-up it calls `/auth/me` to confirm the token is still usable, and a rejected token is discarded, which is how an expired session signs the user out.
- `ProtectedRoute` guards every workspace page and redirects anonymous visitors to `/login`, carrying the requested path so login returns them there. While the stored token is being revalidated it renders a loading state, so refreshing a deep link does not bounce the user to the sign-in form. `PublicOnlyRoute` keeps a signed-in user away from `/login` and `/register`.
- The password policy lives in `frontend/src/features/auth/authPolicy.js` and mirrors the backend contract; the API re-validates regardless.
- The topbar shows the signed-in learner's name, email, and initials, with a sign-out control.

Limitations:

- Logout is stateless. The client discards the token, but the token itself stays valid until `exp`. Add a revocation list keyed on `jti`, or shorten `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, if strict server-side revocation is required.
- There is no rate limiting on `/auth/login` or `/auth/register`, no refresh-token rotation, no email verification, and no password reset. A reverse proxy or API gateway should throttle the auth routes before exposing them publicly.
- `OAuth2PasswordBearer` is configured for the Swagger "Authorize" button, but login accepts a JSON body, so interactive Swagger authorization does not apply.

## API foundation

Current routes:

- `GET /api/v1/health` — liveness and service metadata
- `GET /api/v1/health/ready` — database readiness check
- `POST /api/v1/auth/register` — create an account and issue a token
- `POST /api/v1/auth/login` — verify credentials and issue a token
- `GET /api/v1/auth/me` — current profile for a valid bearer token
- `POST /api/v1/auth/logout` — client-side session termination acknowledgement
- `GET /api/v1/problems` — paginated problem catalog with difficulty and topic filters
- `GET /api/v1/problems/{slug}` — problem detail and examples
- `GET /api/v1/dashboard/summary` — catalog summary for the dashboard
- `GET /api/v1/judge/languages` — the languages this deployment can actually run
- `POST /api/v1/problems/{problem_id}/run` — run a program against the problem's visible cases
- `POST /api/v1/submissions` — judge a program against the visible and hidden cases and store the row
- `GET /api/v1/submissions` — the signed-in learner's submissions, filterable by problem and verdict
- `GET /api/v1/submissions/{submission_id}` — one stored submission, counts and measurements only
- `GET /api/v1/problems/{problem_id}/submissions` — the signed-in learner's submissions for one problem
- `GET /api/v1/progress/me` — the caller's standing across the published catalog
- `GET /api/v1/progress/problems` — every published problem annotated with the caller's status
- `GET /api/v1/progress/problems/{problem_id}` — the caller's record for one problem
- `PUT /api/v1/progress/problems/{problem_id}` — set the caller's status for a problem
- `POST /api/v1/progress/problems/{problem_id}/attempt` — record one more attempt
- `GET /api/v1/algorithms` — the algorithm registry
- `GET /api/v1/algorithms/categories` — the registry grouped by category
- `GET /api/v1/algorithms/problems/{slug}/algorithms` — the algorithms a problem demonstrates
- `GET /api/v1/algorithms/{algorithm_id}` — one algorithm's contract, grammar, and sample inputs
- `POST /api/v1/algorithms/{algorithm_id}/visualize` — trace one algorithm over an input, frame by frame
- `POST /api/v1/algorithms/compare` — trace two algorithms over one input for a side-by-side view
- `GET /api/v1/ai/status` — non-secret AI provider configuration status
- `POST /api/v1/problems/{problem_id}/explanation` — a grounded explanation of the problem
- `POST /api/v1/submissions/{submission_id}/diagnose` — a grounded diagnosis of a stored submission
- `POST /api/v1/code/complexity` — a grounded time/space complexity assessment

That is the complete route surface. Learner progress is described further down under [Learner progress](#learner-progress); the rest are contract-first routes whose behaviour is pinned by the backend and frontend test suites.

AI routes are implemented but fail closed: without a provider credential they answer `503` rather than inventing prose, and `GET /api/v1/ai/status` reports that state so the workspace can label the panels unavailable. Algorithm visualization and comparison run for real. Interview sessions remain reserved for a later phase, and `InterviewsPage` presents the intended workflow rather than simulated results. Code execution is real; see [Code execution](#code-execution).

## Code execution

`POST /api/v1/problems/{problem_id}/run` executes the code in the editor and returns what happened. It is the first half of a judge: it runs the problem's **visible** cases and grades against them, and it deliberately does not record a submission.

Two routes make the contract legible instead of hard-coding it in the UI:

- `GET /api/v1/judge/languages` reports the languages this deployment can run, from the same registry the catalog is validated against. The workspace draws its language tabs from this response, so a language the operator has switched off is never offered.
- `POST /api/v1/problems/{problem_id}/run` accepts `language`, `source_code`, and an optional `stdin`, and returns `verdict`, `cases_run`, `cases_passed`, `cases_total`, per-case results, `error_message`, `total_runtime_ms`, `peak_memory_mb`, `truncated`, and the limits that were applied.

### What runs where

Learner code never runs inside the API process. `backend/app/judge/runner.py` starts one fresh worker per case through `backend/app/judge/worker.py`, which executes the program with `python -I -B` (isolated mode: no user site-packages, no `PYTHON*` environment variables, no working-directory imports), `node`, or `javac` followed by `java`, and exits. The parent owns the clock, the memory ceiling, and the output cap; it never parses the program's stdout to decide anything but truncation.

Per case the job receives the source, the input, and the limits. It does not receive the expected output. A worker therefore cannot learn the answer by reading its own job.

### Honest results

- Verdicts are `accepted`, `wrong_answer`, `runtime_error`, `compilation_error`, `time_limit_exceeded`, `memory_limit_exceeded`, and `failed`, imported from the `SubmissionStatus` model so a label the submission table cannot store can never be published here.
- A run with a learner-supplied `stdin` has no expected output, so it returns `verdict: null`, `cases_run: 0`, and an `ad_hoc` block with the exit code, whether it timed out, and the captured output. It reports what the program did; it does not pretend to have graded it.
- Hidden cases are run and can decide a verdict, but the response only says how many were hidden and whether the program passed them. `case_input`, `expected_output`, and `actual_output` are `None` for a hidden case, so there is nothing to disclose.
- Output is capped, and `truncated` says so. An error message is clipped to the column width rather than failing the write or flooding the response.

### Limits and settings

- `EXECUTION_ENABLED=false` is the kill switch: `/judge/languages` reports `execution_enabled: false` and `/run` answers `503` without starting a process.
- `EXECUTION_PYTHON`, `EXECUTION_JAVASCRIPT`, and `EXECUTION_JAVA` hide a language from the registry, which the workspace follows.
- A problem's own `time_limit_ms` and `memory_limit_mb` are clamped to the model ceilings. The per-case time limit is additionally clamped to `MAX_JUDGE_WALL_CLOCK_MS`, the ceiling on one request's wall clock, so a request cannot multiply the problem's limit by its case count.

### What this is not

This runner is safe against a learner's mistakes — an infinite loop, a runaway allocation, a crash, a flood of output — because those are the cases it is built and tested for. It is **not** a hardened boundary against a determined attacker: no container, no seccomp, no cgroup, no separate user, no network denial. Before accepting untrusted public input, run the worker inside a container or VM (or Windows Job Objects) with no network, a read-only filesystem, and a hard memory limit. On Windows today `RLIMIT_AS` and `RLIMIT_CPU` do not exist, so the memory ceiling is best-effort and `peak_memory_mb` is reported as `null` rather than guessed.

`backend/tests/test_judge.py` covers all of this: 223 tests over real execution, timeouts, output caps, hidden-case non-leakage, budget arithmetic, catalog integrity against reference solutions in Python, JavaScript, and Java, and the absence of any persistence. The integrity test alone judges all 136 reference solutions against every case their problem defines.

## Learner progress

Progress is the only user-specific feature in the API today, and it is scoped to the signed-in learner by the same `get_current_user` guard the auth routes use. There is no `user_id` parameter, query field, or body field anywhere in the progress API: a caller cannot address another learner's progress even by guessing an id.

All five routes require a bearer token:

- `GET /api/v1/progress/me` — the caller's standing across the published catalog
- `GET /api/v1/progress/problems` — every published problem annotated with the caller's status
- `GET /api/v1/progress/problems/{problem_id}` — the caller's record for one problem
- `PUT /api/v1/progress/problems/{problem_id}` — set the caller's status for a problem
- `POST /api/v1/progress/problems/{problem_id}/attempt` — record one more attempt

Behaviour worth knowing:

- Statuses are `not_started`, `attempted`, and `solved`. The vocabulary is enforced on write and in the list filter: an unknown or legacy label such as `completed` is a `422`, never a silent substitution. Legacy values are still *read* correctly, because a row written before this release may still hold one.
- Reading a problem the learner has never opened returns `not_started` without creating a row. Only a problem outside the published catalog is a `404`.
- `GET /progress/problems` covers the whole catalog, so a client can render a complete list from one request. `status`, `difficulty`, and `topic` filter server-side; `limit` and `offset` paginate.
- `PUT` is idempotent. The unique `(user_id, problem_id)` constraint is what makes that true under concurrent requests, so repeated updates leave one record, not two.
- Claiming `attempted` or `solved` implies at least one attempt and stamps the relevant timestamps, so a record cannot contradict itself. Moving back to `not_started` clears the trail instead of leaving a stale solve date behind.
- Recording an attempt on a `solved` problem leaves it solved: re-reading a solution is not a regression.
- `best_runtime_ms` and `best_memory_mb` are optional measurements that only improve. Nothing populates them automatically, because no run writes to a progress row today.

### What progress is not

A status here is self-reported. The API is the durable record of what a learner claims, not of what their code did: pressing **Save submission** records code, and nothing compiles, runs, or grades it. **Run** in the same workspace does execute code, but only against the problem's visible cases, and it writes no submission and no progress row. `best_runtime_ms` stays null until a judged submission flow reports one.

The frontend keeps the two apart on purpose: the record-only actions are labelled as self-reported, and the Run result panel states that a verdict came from the visible cases only.

### Data flow

```text
learner action (mark solved / record an attempt)
  -> ProgressStatusPill + ProblemProgressPanel
  -> useProblemProgress (PUT /progress/problems/{id} or POST /attempt)
  -> progress_service.set_status / record_attempt
  -> Progress row (unique per learner per problem)
  -> GET /progress/me  -> ProgressPanel on the dashboard
```

`useProgressList` feeds the problems page, so the status shown on a card, in the workspace, and on the dashboard always comes from one row.

Frontend layout:

- `frontend/src/features/progress/progressService.js` — the five calls, token-attached
- `frontend/src/features/progress/useProgress.js` — `useProgressSummary`, `useProgressList`, `useProblemProgress`
- `frontend/src/features/progress/progressStatus.js` — label, tone, and formatting for the status vocabulary
- `frontend/src/features/progress/ProgressPanel.jsx` — dashboard summary with difficulty and topic breakdowns
- `frontend/src/features/progress/ProblemProgressPanel.jsx` — the workspace record and its actions
- `frontend/src/features/progress/ProgressStatusPill.jsx` — the shared status pill

### Migrating an existing database

Revision `b_progress_learner_tracking` follows the baseline and is additive: it adds the new columns, rewrites legacy status labels onto the new vocabulary, carries `completed_at` into `solved_at` and `best_time_ms` into `best_runtime_ms`, and creates the composite `(user_id, status)` index. It deletes no row and drops no column, and its `downgrade` is inert, so reversing it cannot destroy learner data.

`AUTO_CREATE_TABLES=true` start-up applies the same shape through `ensure_progress_schema`, so a development database and a migrated database end up identical. The public catalog endpoints stay progress-free: the dashboard's catalog summary is public, and a caller's own progress is only ever available from the authenticated routes above.

## Project conventions

- Keep API request/response types in `backend/app/schemas`.
- Keep persistence and domain orchestration in `database/models` and `backend/app/services`.
- Keep provider integrations behind `backend/app/ai` and execution/visualization contracts behind their respective modules.
- Hash passwords through `backend/app/core/security.py`; never store or log plaintext credentials.
- Never execute user-submitted code in the API process. Execution belongs to `backend/app/judge`, and a worker must be started from a deployment that provides a real OS-level boundary.
- Never log or return `AI_API_KEY`, `JWT_SECRET_KEY`, or other credentials.
