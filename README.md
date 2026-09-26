# ALgotwin

ALgotwin is a production-oriented foundation for an AI-powered DSA learning, visualization, and interview platform. The repository provides a runnable web shell, a FastAPI REST API, persistent user accounts with bearer-token authentication, database-ready models, environment configuration, and the boundaries needed for future secure code execution, AI explanations, algorithm visualization, and interview features.

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
  app/algorithms/           algorithm execution contracts and registry
  app/visualization/        visualization data contracts
  app/ai/                   AI provider boundary and configuration
  tests/                    backend tests
database/
  models/                   SQLAlchemy domain models
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
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Start the frontend in another terminal:

```powershell
npm run dev:frontend
```

Open `http://localhost:5173`. The API root is `http://localhost:8000`; health and readiness endpoints are under `http://localhost:8000/api/v1/health` and `http://localhost:8000/api/v1/health/ready`.

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
- `GET /api/v1/algorithms` — algorithm registry contract
- `GET /api/v1/ai/status` — non-secret AI provider configuration status

Secure code execution, AI generation, and interview state are intentionally reserved for the next implementation phase. The frontend displays these boundaries rather than presenting simulated execution or learning results.

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
- `best_runtime_ms` and `best_memory_mb` are optional measurements that only improve. Nothing populates them automatically, because AlgoTwin has no runner yet.

### What progress is not

A status here is self-reported. No code is compiled, run, or graded, and the workspace panel says so in the product. The API is the durable record that a future sandboxed runner can write to; it is not a verdict system pretending to be one. `best_runtime_ms` stays null until a real runner reports one.

The frontend labels these actions as self-reported and leaves the run button disabled, so nothing in the UI implies execution that does not exist.

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
- Never execute user-submitted code in the API process; add a sandboxed worker before enabling execution.
- Never log or return `AI_API_KEY`, `JWT_SECRET_KEY`, or other credentials.
