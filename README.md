# ALgotwin

ALgotwin is a production-oriented foundation for an AI-powered DSA learning, visualization, and interview platform. The repository provides a runnable web shell, a FastAPI REST API, persistent user accounts with bearer-token authentication, database-ready models, environment configuration, and the boundaries needed for future secure code execution, AI explanations, algorithm visualization, and interview features.

## Stack

- Frontend: React, Vite, React Router, Monaco Editor, Recharts, ESLint, Vitest
- Backend: FastAPI, Pydantic Settings, SQLAlchemy 2, PyJWT, pwdlib (Argon2)
- Database: SQLite locally, PostgreSQL through `DATABASE_URL`
- Migrations: Alembic scaffold for environment-to-environment upgrades

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
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

The Alembic configuration expects the project root as its working directory. Do not commit `.env`, database files, or AI keys.

## Authentication

`POST /api/v1/auth/register` and `POST /api/v1/auth/login` return a short-lived bearer token plus the public profile; `GET /api/v1/auth/me` resolves the profile from that token and `POST /api/v1/auth/logout` returns `204`.

- Passwords are hashed with Argon2 through `pwdlib` and are never returned by the API.
- Tokens are HS256 JWTs carrying `sub`, `email`, and `exp`; the signing secret comes from `JWT_SECRET_KEY` and the lifetime from `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.
- Emails are compared case-insensitively and stored lowercase, so `Ada@example.com` and `ada@example.com` are the same account.
- `AUTO_CREATE_TABLES=true` and startup also apply an idempotent `users` compatibility upgrade: a legacy table with `display_name` is rebuilt into `name`, `email`, `password_hash`, `created_at`, `updated_at` while preserving existing rows, IDs, and dependent `progress` rows. Legacy rows keep a null `password_hash` and must use a password reset flow.
- Logout is stateless. The client discards the token, but the token itself stays valid until `exp`; add a revocation list or shorten `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` if strict server-side revocation is required.

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

Secure code execution, progress mutations, AI generation, and interview state are intentionally reserved for the next implementation phase. The frontend displays these boundaries rather than presenting simulated execution or learning results.

## Project conventions

- Keep API request/response types in `backend/app/schemas`.
- Keep persistence and domain orchestration in `database/models` and `backend/app/services`.
- Keep provider integrations behind `backend/app/ai` and execution/visualization contracts behind their respective modules.
- Hash passwords through `backend/app/core/security.py`; never store or log plaintext credentials.
- Never execute user-submitted code in the API process; add a sandboxed worker before enabling execution.
- Never log or return `AI_API_KEY`, `JWT_SECRET_KEY`, or other credentials.
