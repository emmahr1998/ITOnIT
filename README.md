# ITOnIT

**ITOnIT** is a multi-tenant IT service/ticket and inventory management system.
Each customer organization ("company") gets its own isolated workspace: employees
report issues as structured tickets, technicians triage and resolve them —
reserving and consuming IT inventory against a ticket where relevant — and
Company Administrators manage users, reference data, inventory, and company
settings. Every meaningful change is recorded in a full audit trail. A separate,
platform-level System Administrator provisions and oversees companies from
outside any one tenant. The same application ships as a web app and as a
Windows desktop app (Electron).

This repository contains four parts:

- **`backend/`** — a FastAPI REST API with multi-tenant data isolation,
  role-based permissions, JWT authentication, and a SQL Server database managed
  through Alembic migrations.
- **`frontend/`** — a React + TypeScript single-page app that consumes that
  API: a public landing page, self-service company registration and login, a
  role-aware dashboard/ticket/inventory workflow, company administration, and
  a separate platform-administration console.
- **`desktop/`** — a thin Electron shell that loads the exact same React app as
  a Windows desktop application, talking to an external ITOnIT backend.
- **`docs/`** — technical documentation: architecture, the API guide, ER/flow
  diagrams, a professor demo script, and a technical-debt/limitations log.

For a deep technical dive into the backend, see [`docs/`](docs/) — in
particular `docs/BACKEND_SUMMARY.md` (a 5–10 minute read) and
`docs/PROFESSOR_DEMO_GUIDE.md` (a live, step-by-step walkthrough). For the
frontend, see [`frontend/README.md`](frontend/README.md).

---

## Features

- **Multi-tenancy** — every company's users, tickets, reference data, and
  inventory are isolated from every other company's, enforced at the
  repository layer (`CompanyScopedRepository`), never left to individual
  queries to remember.
- **Public website** — an unauthenticated visitor sees a landing page and an
  About page with links to sign in or register; no ticket, inventory, or
  account data is ever exposed without logging in.
- **Company registration** — anyone can register a new company (`POST
  /companies/register`), which creates the company, its first Company
  Administrator, and starter reference data (priorities, ticket categories, a
  location, a department, inventory categories) in one transaction, then signs
  the new admin in immediately. Employees and Technicians never self-register —
  only a Company Administrator can create them, through `POST /users`.
- **Authentication** — company-code resolution, then username/email + password
  login, Argon2 password hashing, JWT access tokens (short-lived) and refresh
  tokens (longer-lived) with distinct, non-interchangeable token types, and a
  client-side silent-refresh flow so a page reload doesn't force a re-login.
  Logout is client-side only (clears local tokens) — see
  `docs/TECH_DEBT.md` for why there is no server-side revocation in V1.
- **Role-based permissions** — three company-level roles (Employee,
  Technician, Company Administrator — any number of Company Administrators
  may exist per company, all with identical permissions), plus a
  platform-level System Administrator with its own dedicated login and
  console, each with a precisely defined and enforced set of allowed actions
  on both the API and the frontend.
- **User management** — admin-managed accounts (create, edit, deactivate — no
  hard delete, to preserve ticket/comment/audit history and attribution),
  self-service profile editing (safe fields only), self-service and
  admin-driven password changes.
- **Reference data management** — Departments, Priorities, Categories, and
  Locations, each company-owned and manageable through their own CRUD
  endpoints and admin pages.
- **Ticket lifecycle** — creation, category/priority/location assignment,
  technician assignment, a controlled status workflow (`NEW → ASSIGNED →
  IN_PROGRESS ⇄ WAITING_FOR_EMPLOYEE → RESOLVED → CLOSED`), comments, and file
  attachments (attached to the ticket directly, never to a comment), with
  ticket deletion restricted to Company Administrator.
- **Inventory management** — SERIALIZED assets (laptops, monitors — one
  physical unit per row, asset-tag required) and BULK stock (cables, mice —
  quantity-based), each with its own tracking rules; reserve/consume/release
  against a ticket, a permanent append-only transaction history per item, and
  low-stock/warranty-expiring filtering.
- **Full audit trail** — every meaningful ticket change (field edits,
  assignment, status changes, comments, attachments, inventory
  reserve/consume/release) is recorded as a structured history entry: who,
  what changed, old value, new value, when. Inventory items separately carry
  their own permanent, append-only transaction log.
- **Analytics & dashboard** — role-scoped ticket analytics (status/priority/
  category breakdowns, a 6-month created/resolved trend, high-priority-open
  and unassigned counts) and inventory analytics (full company-wide picture
  for Company Administrator, a narrower "reserved for my tickets" view for
  Technician), computed only from real backend data.
- **Platform administration** — a separate System Administrator role
  (`company_id IS NULL`) with its own login (`POST /platform/login`) and
  console: a platform overview, a searchable company list and detail view,
  activating/deactivating a company, and provisioning new companies on a
  customer's behalf.
- **Windows desktop app** — the same React frontend, shipped as an Electron
  app (NSIS installer + portable executable), talking to an external ITOnIT
  backend over HTTP — Electron bundles neither FastAPI nor SQL Server.
- **Auto-generated API documentation** — the full OpenAPI schema and an
  interactive Swagger UI, generated directly from the code.

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
| Backend testing | `pytest` |
| Backend linting | `ruff` |
| Backend server | `uvicorn` |
| Frontend | React 19 + TypeScript (`strict: true`) |
| Frontend build tool | Vite |
| Frontend routing | React Router v7 |
| Frontend HTTP client | Axios |
| Frontend icons | lucide-react |
| Frontend styling | CSS Modules + a shared design-token stylesheet (no UI library) |
| Frontend linting | `oxlint` |
| Desktop shell | Electron, packaged with `electron-builder` (Windows: NSIS + portable) |

See `backend/requirements.txt` / `backend/requirements-dev.txt`,
`frontend/package.json`, and `desktop/package.json` for exact pinned versions.

## Project structure

```
ITOnIT/
├── docs/                        Technical documentation (architecture, API guide,
│                                diagrams, demo guide, Q&A, technical debt)
├── README.md                    This file
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app creation, CORS, router mounting
│   │   ├── api/
│   │   │   ├── router.py         Combines every route module into one router
│   │   │   └── routes/           One file per resource (auth, companies, platform,
│   │   │                         tickets, users, inventory-*, analytics, ...)
│   │   ├── core/                 Settings (config.py), security (hashing, JWT), time (UTC helpers)
│   │   ├── db/                   SQLAlchemy engine, session factory, declarative Base
│   │   ├── models/                SQLAlchemy ORM models (15 tables, one file per table)
│   │   ├── schemas/               Pydantic request/response models + shared validators
│   │   ├── repositories/          Persistence-only classes (CompanyScopedRepository, never commit)
│   │   ├── services/              Business logic, transaction boundaries, domain exceptions
│   │   ├── dependencies/          FastAPI DI wiring: auth, roles, company scoping, DB session
│   │   └── scripts/               Maintenance scripts (e.g. seed_initial_data.py)
│   ├── scripts/                   Dev-only helper scripts outside the app package
│   ├── alembic/                   Migration environment and version history
│   ├── storage/                   Uploaded attachments and company logos (not committed)
│   └── tests/                     pytest suite (conftest.py + one file per feature)
├── frontend/
│   └── src/
│       ├── api/                   Axios client + one module per backend resource
│       ├── auth/                  AuthContext/AuthProvider, ProtectedRoute, PlatformProtectedRoute
│       ├── components/            common/ admin/ layout/ tickets/ — see frontend/README.md
│       ├── pages/                 One component per route (tenant + platform/)
│       ├── router/                AppRouter — route definitions and role gating
│       ├── types/                 TypeScript types mirroring the backend's schemas
│       └── styles/                Design tokens and shared classes
└── desktop/
    ├── main.js                    Electron main process: window, app:// protocol, dev/prod origin
    └── package.json                electron-builder config (NSIS + portable, Windows)
```

## Installation

**Prerequisites:**
- Python 3.12+
- Node.js 20+ and npm
- Microsoft SQL Server (Express edition is fine), with the Microsoft ODBC
  Driver for SQL Server installed (`ODBC Driver 17 for SQL Server` or
  compatible — see `DATABASE_DRIVER` below)
- Git
- Windows is only required to *build or run the packaged Electron installer*;
  the backend, frontend, and `npm run dev`/`electron .` desktop dev mode all
  run cross-platform.

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

## Database setup

The target SQL Server database must **exist** before Alembic can connect to
it — migrations create tables inside a database, not the database itself.
Create an empty database once, from SSMS or `sqlcmd`:

```sql
CREATE DATABASE ITOnIT;
```

(use whatever name you put in `DATABASE_NAME` below — `ITOnIT` is just the
`.env.example` default). Never create or alter tables manually after that —
every schema change from here on goes through a reviewed Alembic migration
script in `backend/alembic/versions/`.

## Environment variables

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in your own values —
`.env` is git-ignored and must never be committed.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `APP_NAME` | no | `ITOnIT API` | Shown in Swagger/OpenAPI |
| `APP_VERSION` | no | `1.0.0` | Shown in Swagger/OpenAPI |
| `DATABASE_SERVER` | **yes** | — | SQL Server host (e.g. `localhost\SQLEXPRESS`) |
| `DATABASE_NAME` | **yes** | — | Database name — must already exist, see above |
| `DATABASE_DRIVER` | no | `ODBC Driver 17 for SQL Server` | Must match an installed ODBC driver |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | no | unset | Leave both unset to use Windows Trusted Connection |
| `SECRET_KEY` | **yes** | — | Signs every JWT — use a long, random value, never the example placeholder |
| `ALGORITHM` | no | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `10080` (7 days) | Refresh token lifetime |
| `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` / `INITIAL_ADMIN_FIRST_NAME` / `INITIAL_ADMIN_LAST_NAME` | no | unset | Optional: seeds one admin user on the Default Company via `seed_initial_data`, if all set |
| `PLATFORM_ADMIN_EMAIL` / `PLATFORM_ADMIN_PASSWORD` / `PLATFORM_ADMIN_FIRST_NAME` / `PLATFORM_ADMIN_LAST_NAME` | no | unset | Optional: seeds the one platform-level System Administrator account (`POST /platform/login`) via the same script, if all set |
| `ATTACHMENT_STORAGE_PATH` | no | `storage/attachments` | Where uploaded ticket files are written, relative to `backend/` |
| `MAX_ATTACHMENT_SIZE_BYTES` | no | `10485760` (10 MB) | Upload size cap |
| `LOGO_STORAGE_PATH` | no | `storage/logos` | Where uploaded company logos are written |
| `MAX_LOGO_SIZE_BYTES` | no | `2097152` (2 MB) | Logo upload size cap |
| `CORS_ORIGINS` | no | `["http://localhost:5173","http://localhost:3000"]` | JSON array of browser origins allowed to call the API |

`CORS_ORIGINS` must list every origin a client actually runs from — never `*`
or `null`. For local web development that's `http://localhost:5173`; to also
serve the Electron desktop app, add its exact custom-protocol origin,
`app://itonit`:

```
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000","app://itonit"]
```

Never put a real production secret in `backend/.env.example` — it is
committed and must stay a template with blank/placeholder values.

### Frontend (`frontend/.env.development`, `.env.local`, or `.env.desktop`)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the backend, no trailing slash (e.g. `http://localhost:8000`) |
| `VITE_APP_MODE` | Leave unset (or `web`) for the browser build. Set to `desktop` for the Electron build — see "Desktop app" below |

Vite bundles every `VITE_`-prefixed variable into the client-side JavaScript —
never put a secret in one.

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
The app is now live at `http://localhost:5173` and talks to the backend at the
URL in `VITE_API_BASE_URL`. Visiting `/` shows the public landing page;
`/register` and `/login` are also reachable without an account. A System
Administrator signs in separately at `/platform/login`.

### Desktop app (Windows, Electron)

`desktop/` is a thin Electron shell around the same React app (a separate npm
package; the renderer source stays in `frontend/`). It opens at the company
login instead of the public site. FastAPI and SQL Server are **not** bundled —
the desktop app talks to a backend you run separately (the demo build points
at `http://localhost:8000`, see `frontend/.env.desktop`).

For development: run the backend, then in `frontend/` run
```bash
npm run dev:desktop
```
which starts the Vite dev server in desktop mode (`VITE_APP_MODE=desktop`),
then in a second terminal, in `desktop/`:
```bash
npm install
npm run dev
```
`electron .` loads that dev server at its normal `http://localhost:5173`
origin. `npm start` (`electron . --prod`) instead loads the *built* renderer
from `frontend/dist-desktop`, served from the custom `app://itonit` origin —
build it first with `npm run build:desktop` in `frontend/`.

To produce the distributable Windows installer:
```bash
cd desktop
npm run dist        # builds the desktop renderer, then release/ITOnIT-<version>-x64-setup.exe + -portable.exe
```

The desktop app's production origin is `app://itonit`, so the backend's
`CORS_ORIGINS` must include it exactly (see the environment-variables section
above — never `*` or `null`).

The Windows build is an **unsigned**, university/demo build with **no
auto-updater and no code signing** — Windows SmartScreen may show a warning
("Windows protected your PC" — choose *More info*, then *Run anyway*).

## Running migrations

```bash
cd backend
python -m alembic upgrade head          # apply every migration up to the latest
python -m alembic current               # show the database's current revision
python -m alembic heads                 # confirm there is exactly one head
python -m alembic check                 # verify models match the database, no drift
```

Never create or alter tables manually in SQL Server Management Studio — all
schema changes go through a reviewed Alembic migration script in
`backend/alembic/versions/`.

### Seeding data

```bash
python -m app.scripts.seed_initial_data   # roles + Default Company's priorities (+ optional admin, + optional platform admin)
python scripts/create_demo_users.py       # four demo accounts on the Default Company (dev only)
python -m app.scripts.seed_demo_data      # a full demo company + tickets + inventory (dev/demo only)
```

All three are idempotent — safe to run repeatedly, they skip anything that
already exists (matched by company code / username / title / asset tag,
never a hardcoded id), so re-running the whole sequence before a demo or
after pulling latest never creates duplicates. `seed_demo_data` is the
newest of the three (Phase 14.4) and is independent of the other two: it
registers its own dedicated **ITOnIT Demo Co** (`DEMO001`) through the real
`POST /companies/register` path — a Company Administrator, a Technician, two
Employees, ~12 tickets spanning every status, and a small inventory catalog
(both SERIALIZED and BULK items, with real reserve/consume/release history)
— rather than adding data to `create_demo_users.py`'s `DEFAULT001` company,
so the two demo datasets never interfere with each other. See
`docs/PROFESSOR_DEMO_GUIDE.md` for the exact accounts/tickets/items it
produces and the live-demo story built around it.

Anyone can also register a brand new company from the app itself via the
public landing page → **Register Company** (`/register`, `POST
/companies/register`) — no seed script required for that path.

### Default accounts

`python scripts/create_demo_users.py` (run from `backend/`) creates four demo
accounts on the `DEFAULT001` company, for local development and demos only —
two Company Administrators (to demonstrate that the role isn't singular), one
Technician, one Employee:

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin123!` | Company Administrator |
| `admin2` | `Admin2Pass123!` | Company Administrator |
| `technician` | `Technician123!` | Technician |
| `employee` | `Employee123!` | Employee |

The one platform-level System Administrator account is seeded separately, via
the `PLATFORM_ADMIN_*` environment variables and `seed_initial_data` (see
above) — there is no fixed default password for it, since it is never
committed to this repository.

## Running tests

**Backend:**
```bash
cd backend
pytest                    # run the whole suite
pytest -q                 # quiet summary
ruff check app tests scripts  # lint
python -m alembic check   # verify no model/migration drift
```
The test suite does not require a real database connection — every service
accepts its repository as a swappable argument, and tests inject small
in-memory fakes instead.

**Frontend:**
```bash
cd frontend
npx tsc -b       # type-check (strict mode)
npm run lint     # oxlint
npm run build    # full production (web) build
npm run build:desktop  # production build for the Electron renderer
```
There is no automated frontend component/E2E test suite in V1 — type-checking,
linting, and a full production build are the frontend's automated checks; UI
behavior is verified manually (see `docs/PROFESSOR_DEMO_GUIDE.md`). See
`docs/TECH_DEBT.md`.

**Desktop:**
```bash
cd desktop
node --check main.js   # syntax-check the Electron main process
npm audit               # dependency vulnerability check
```

## API documentation

- **Interactive**: `http://127.0.0.1:8000/docs` (Swagger UI) while the server is running.
- **Written reference**: [`docs/BACKEND_API_GUIDE.md`](docs/BACKEND_API_GUIDE.md) —
  endpoint-by-endpoint (who can call it, request/response shape, every possible error).
- **Architecture deep dive**: [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md).
- **Database design**: [`docs/database-design.md`](docs/database-design.md).
- **Diagrams**: [`docs/BACKEND_DIAGRAMS.md`](docs/BACKEND_DIAGRAMS.md) (architecture, auth
  flow, ER diagram, ticket lifecycle, inventory flow, attachment upload flow, request-processing flow).
- **Demo script**: [`docs/PROFESSOR_DEMO_GUIDE.md`](docs/PROFESSOR_DEMO_GUIDE.md).
- **Q&A**: [`docs/PROFESSOR_QA.md`](docs/PROFESSOR_QA.md).
- **Technical debt / V1 limitations**: [`docs/TECH_DEBT.md`](docs/TECH_DEBT.md).
- **Frontend specifics**: [`frontend/README.md`](frontend/README.md).
