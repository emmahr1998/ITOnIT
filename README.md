# ITOnIT

**ITOnIT** is a full-stack internal IT support ticket management system. It replaces
ad-hoc phone calls, emails, and chat messages to the IT department with a single,
auditable workflow: employees report issues as structured tickets, technicians and
managers triage and resolve them, and every meaningful change is recorded in a full
audit trail.

This repository contains both halves of the application:

- **`backend/`** — a FastAPI REST API with role-based permissions, JWT authentication,
  and a SQL Server database managed through Alembic migrations.
- **`frontend/`** — a React + TypeScript single-page app that consumes that API: a
  public landing page, self-service registration and login, and a role-aware dashboard
  and ticket workflow for Employees, Technicians, and Company Administrators.

For a deep technical dive into the backend specifically, see the [`docs/`](docs/)
folder — in particular `docs/BACKEND_SUMMARY.md` (5–10 minute read) and
`docs/PROFESSOR_DEMO_GUIDE.md` (a live, step-by-step Swagger walkthrough). For the
frontend, see [`frontend/README.md`](frontend/README.md).

---

## Features

- **Public landing page** — an unauthenticated visitor sees a marketing-style
  overview with links to sign in or register; no ticket or account data is ever
  exposed without logging in.
- **Self-service registration** — anyone can create an account (`POST
  /auth/register`), always as an Employee; the higher roles (Technician, Company
  Administrator) can only be granted by a Company Administrator through `POST /users`.
- **Authentication** — username/email + password login, Argon2 password hashing, JWT
  access tokens (short-lived) and refresh tokens (long-lived) with distinct,
  non-interchangeable token types, and a client-side silent-refresh flow so a page
  reload doesn't force a re-login.
- **Role-based permissions** — three company-level roles (Employee, Technician,
  Company Administrator — any number of Company Administrators may exist per
  company, all with identical permissions), plus a platform-level System
  Administrator role reserved for future platform-management use, each with a
  precisely defined and enforced set of allowed actions, enforced independently
  on both the API (role checks + per-resource ownership checks) and the
  frontend (route guards, hidden nav links).
- **User management** — admin-managed accounts (create, edit, deactivate — no hard
  delete, to preserve ticket/comment history and audit attribution), self-service
  profile editing (safe fields only), self-service and admin-driven password changes.
- **Reference data management** — Departments, Priorities, Categories, and Locations,
  each manageable through their own CRUD endpoints and admin pages.
- **Ticket lifecycle** — creation, category/priority/location assignment, technician
  assignment, a controlled status workflow (`NEW → ASSIGNED → IN_PROGRESS ⇄
  WAITING_FOR_EMPLOYEE → RESOLVED → CLOSED`), comments, and file attachments, with
  ticket deletion restricted to Company Administrator.
- **Full audit trail** — every meaningful ticket change (field edits, assignment,
  status changes, comments, attachments) is recorded as a structured history entry:
  who, what changed, old value, new value, when.
- **File attachments** — validated multipart uploads (type/size checked), stored on
  disk with randomly generated filenames (the client-supplied filename is never
  trusted for storage), with only metadata kept in the database.
- **Role-aware dashboard** — each role sees a different set of stat cards, charts,
  and quick actions, computed only from real backend data (no fabricated metrics);
  every ticket-related stat card is clickable and deep-links into a filtered ticket
  list.
- **Auto-generated API documentation** — the full OpenAPI schema and an interactive
  Swagger UI, generated directly from the code, with zero hand-written documentation
  to keep in sync.

## Technology stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.12 |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Database | Microsoft SQL Server (via `pyodbc`) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Backend auth | JWT (`PyJWT`), access + refresh tokens |
| Password hashing | Argon2 (`pwdlib`) |
| File uploads | `python-multipart` |
| Backend testing | `pytest`, `httpx`/`TestClient` |
| Backend linting | `ruff` |
| Backend server | `uvicorn` |
| Frontend | React 19 + TypeScript (`strict: true`) |
| Frontend build tool | Vite |
| Frontend routing | React Router v7 |
| Frontend HTTP client | Axios |
| Frontend icons | lucide-react |
| Frontend styling | CSS Modules + a shared design-token stylesheet (no UI library) |
| Frontend linting | `oxlint` |

See `backend/requirements.txt` / `backend/requirements-dev.txt` and
`frontend/package.json` for exact pinned versions.

## Project structure

```
ITOnIT/
├── docs/                        Full backend technical documentation (see below)
├── README.md                    This file
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app creation, CORS, router mounting
│   │   ├── api/
│   │   │   ├── router.py         Combines every route module into one router
│   │   │   └── routes/           One file per resource (auth, users, tickets, ...)
│   │   ├── core/                 Settings (config.py) and security (hashing, JWT)
│   │   ├── db/                   SQLAlchemy engine, session factory, declarative Base
│   │   ├── models/                SQLAlchemy ORM models (one file per table)
│   │   ├── schemas/               Pydantic request/response models + shared validators
│   │   ├── repositories/          Persistence-only classes (build queries, never commit)
│   │   ├── services/              Business logic, transaction boundaries, domain exceptions
│   │   ├── dependencies/          FastAPI DI wiring: auth, roles, db session, per-resource services
│   │   └── scripts/               Maintenance scripts (e.g. seed_initial_data.py)
│   ├── scripts/                   Dev-only helper scripts outside the app package
│   ├── alembic/                   Migration environment and version history
│   ├── storage/attachments/       Uploaded file storage (not committed)
│   └── tests/                     pytest suite (conftest.py + one file per feature)
└── frontend/
    └── src/
        ├── api/                   Axios client + one module per backend resource
        ├── auth/                  AuthContext/AuthProvider, ProtectedRoute
        ├── components/            common/ admin/ layout/ tickets/ — see frontend/README.md
        ├── pages/                 One component per route
        ├── router/                AppRouter — route definitions and role gating
        ├── types/                 TypeScript types mirroring the backend's schemas
        └── styles/                Design tokens and shared classes
```

## Installation

**Prerequisites:**
- Python 3.12+
- Node.js 20+ and npm
- Microsoft SQL Server (Express edition is fine) with an ODBC driver installed
  (`ODBC Driver 17 for SQL Server` or compatible)

**Backend setup:**

```bash
cd backend
python -m venv .venv
```
Activate the virtual environment (`.venv\Scripts\activate` on Windows,
`source .venv/bin/activate` on macOS/Linux), then:
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

**Frontend setup:**

```bash
cd frontend
npm install
```

## Environment variables

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in your own values — `.env` is
git-ignored and must never be committed.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `APP_NAME` | no | `ITOnIT API` | Shown in Swagger/OpenAPI |
| `APP_VERSION` | no | `1.0.0` | Shown in Swagger/OpenAPI and `GET /health` |
| `DATABASE_SERVER` | **yes** | — | SQL Server host (e.g. `localhost\SQLEXPRESS`) |
| `DATABASE_NAME` | **yes** | — | Database name |
| `DATABASE_DRIVER` | no | `ODBC Driver 17 for SQL Server` | Must match an installed ODBC driver |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | no | unset | Leave both unset to use Windows Trusted Connection |
| `SECRET_KEY` | **yes** | — | Signs every JWT — use a long, random value, never the example placeholder |
| `ALGORITHM` | no | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `10080` (7 days) | Refresh token lifetime |
| `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` / `INITIAL_ADMIN_FIRST_NAME` / `INITIAL_ADMIN_LAST_NAME` | no | unset | Optional: seeds one admin user via `seed_initial_data` if all set |
| `ATTACHMENT_STORAGE_PATH` | no | `storage/attachments` | Where uploaded files are written, relative to `backend/` |
| `MAX_ATTACHMENT_SIZE_BYTES` | no | `10485760` (10 MB) | Upload size cap |
| `CORS_ORIGINS` | no | `["http://localhost:5173","http://localhost:3000"]` | JSON array of browser origins allowed to call the API — add your deployed frontend's URL here before deploying |

### Frontend (`frontend/.env.development` or `.env.local`)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the backend, no trailing slash (defaults to `http://localhost:8000` in the committed `.env.development`) |

Remember that Vite bundles every `VITE_`-prefixed variable into the client-side
JavaScript — never put a secret in one.

## Running locally

**Backend:**
```bash
cd backend
uvicorn app.main:app --reload
```
The API is now live at `http://127.0.0.1:8000`. Swagger UI is at
`http://127.0.0.1:8000/docs`; the raw OpenAPI schema is at `/openapi.json`.

**Frontend** (in a second terminal):
```bash
cd frontend
npm run dev
```
The app is now live at `http://localhost:5173` and talks to the backend at the URL in
`VITE_API_BASE_URL`. Visiting `/` shows the public landing page; `/register` and
`/login` are also reachable without an account.

## Running migrations

```bash
cd backend
python -m alembic upgrade head          # apply every migration up to the latest
python -m alembic current               # show the database's current revision
python -m alembic check                 # verify models match the database, no drift
```

Never create or alter tables manually in SQL Server Management Studio — all schema
changes go through a reviewed Alembic migration script in `backend/alembic/versions/`.

### Seeding data

```bash
python -m app.scripts.seed_initial_data   # roles + default priorities (+ optional admin)
python scripts/create_demo_users.py       # four demo accounts (dev only)
```

Both are idempotent — safe to run repeatedly, they skip anything that already exists.

## Default accounts

`python scripts/create_demo_users.py` (run from `backend/`) creates four demo
accounts, for local development and demos only - two Company Administrators
(to demonstrate that the role isn't singular), one Technician, one Employee:

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin123!` | Company Administrator |
| `admin2` | `Admin2Pass123!` | Company Administrator |
| `technician` | `Technician123!` | Technician |
| `employee` | `Employee123!` | Employee |

Anyone can also create their own Employee-role account from the app itself via the
public landing page → **Create account** (`/register`) — no seed script required for
that path.

## Running tests

**Backend:**
```bash
cd backend
pytest                    # run the whole suite
pytest -q                 # quiet summary
pytest tests/test_auth.py # a single file
ruff check app tests      # lint
```
The test suite does not require a real database connection — every service accepts
its repository as a swappable argument, and tests inject small in-memory fakes
instead.

**Frontend:**
```bash
cd frontend
npx tsc -b       # type-check (strict mode)
npm run lint     # oxlint
npm run build    # full production build
```

## API documentation

- **Interactive**: `http://127.0.0.1:8000/docs` (Swagger UI) while the server is running.
- **Written reference**: [`docs/BACKEND_API_GUIDE.md`](docs/BACKEND_API_GUIDE.md) —
  endpoint-by-endpoint (who can call it, request/response shape, every possible error).
- **Architecture deep dive**: [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md).
- **Diagrams**: [`docs/BACKEND_DIAGRAMS.md`](docs/BACKEND_DIAGRAMS.md) (architecture, auth
  flow, ER diagram, ticket lifecycle, attachment upload flow, request-processing flow).
- **Demo script**: [`docs/PROFESSOR_DEMO_GUIDE.md`](docs/PROFESSOR_DEMO_GUIDE.md).
- **Q&A**: [`docs/PROFESSOR_QA.md`](docs/PROFESSOR_QA.md).
- **Frontend specifics**: [`frontend/README.md`](frontend/README.md).
