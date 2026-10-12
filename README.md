# Vantra

AI-powered forex and crypto trading strategy platform: backtest, optimize and validate trading strategies, including ones written in plain English. B.Tech major project, Department of Artificial Intelligence, SATI Vidisha.

## Status

| Area | Status |
|---|---|
| Authentication (signup, login, JWT access token, httpOnly refresh cookie, protected routes) | Done |
| Login/signup UI, auth state (Zustand) | Done |
| Charting, market data, indicators | Planned (Phase 2-3) |
| Backtesting, optimization, walk-forward validation | Planned (Phase 4+) |
| LLM strategy parser, SMC/ICT scoring | Planned |

## Tech stack

- Frontend: React (Vite), React Router, Zustand
- Backend: FastAPI, SQLAlchemy, Pydantic, bcrypt, PyJWT
- Database: PostgreSQL 16
- Tests: pytest

## Prerequisites

macOS with Homebrew, Python 3.10+, Node.js 18+, PostgreSQL 16, Git.

## Setup

### 1. Database

```bash
brew services start postgresql@16
createdb vantra_dev
psql vantra_dev -f backend/db/schema.sql
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `backend/.env` and set `DATABASE_URL` (your Postgres user) and `SECRET_KEY`. Generate a key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run the API on port 8001:

```bash
uvicorn main:app --reload --port 8001
```

API docs: http://localhost:8001/docs

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5180 (use `localhost`, not `127.0.0.1`, so the refresh cookie works).

## Environment variables

Backend (`backend/.env`):

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL |
| `SECRET_KEY` | Secret used to sign JWTs. Never commit it |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime (default 30) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime (default 7) |
| `COOKIE_SECURE` | `true` in production (HTTPS), `false` locally |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |

Frontend (`frontend/.env`): `VITE_API_URL` is the backend URL, for example `http://localhost:8001`.

## Running the tests

Create the test database once:

```bash
createdb vantra_test
psql vantra_test -f backend/db/schema.sql
```

Then:

```bash
cd backend
source venv/bin/activate
pytest -v
```

Tests run against `vantra_test` only and refuse to run against any database whose name does not end with `_test`.

## Project structure

```
backend/
  main.py              FastAPI app, CORS, health check
  app/
    config.py          settings from .env
    database.py        engine, session, get_db()
    models.py          User model
    schemas.py         request/response schemas
    security.py        bcrypt + JWT helpers
    dependencies.py    get_current_user (route protection)
    routers/auth.py    signup, login, refresh, logout, me
  db/schema.sql        table definitions
  tests/               pytest tests
frontend/
  src/
    api.js             fetch wrapper for the backend
    authedRequest.js   authenticated requests with auto refresh
    store/authStore.js Zustand auth state
    components/        layout, fields, icons, route guards
    pages/             login, signup, dashboard
```

## Auth design

- Access token (JWT, 30 min) is kept in memory only.
- Refresh token (JWT, 7 days) is an httpOnly, SameSite cookie scoped to `/api/auth`.
- On page load the app silently calls `/api/auth/refresh` to restore the session.
- A 401 on an authenticated request triggers one automatic refresh and retry.

## Known limitations

- Refresh tokens are stateless: logging out clears the cookie, but a stolen token stays valid until it expires. Production hardening would store refresh tokens and rotate them.
- No rate limiting on login yet.
- Trading features are not implemented yet (see Status).
