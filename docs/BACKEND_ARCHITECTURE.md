# ITOnIT Backend — Architecture Reference

This document is a complete technical explanation of the ITOnIT backend, based on a direct
inspection of the code in `backend/`. Every claim below points at an exact file, class, or
function. Where the code does not answer a question, this document says **"Not confirmed
from the code"** instead of guessing.

Stack confirmed from `backend/requirements.txt`: Python, **FastAPI 0.139.2**, **SQLAlchemy
2.0.51**, **pyodbc 5.3.0** (SQL Server driver), **Alembic 1.18.5**, **Pydantic 2.13.4** +
**pydantic-settings 2.14.2**, **PyJWT 2.13.0**, **pwdlib[argon2] 0.3.0** (password hashing),
**python-multipart 0.0.32** (file uploads), **uvicorn 0.51.0**. Dev/test tools (from
`requirements-dev.txt`): **pytest 9.1.1**, **httpx 0.28.1**, **ruff 0.15.22**.

---

## 1. Backend overview

**What the backend is responsible for.** ITOnIT's backend is the entire server side of an
internal IT support ticket system: it authenticates users, enforces who is allowed to do
what, stores and retrieves all data in SQL Server, validates every request and response, and
serves a JSON HTTP API that a frontend (or Swagger, or `curl`) talks to. It has no
server-rendered HTML pages — it is a pure API.

**How FastAPI is used.** The single `FastAPI()` application object is created once, in
`app/main.py`. Every URL the API exposes is defined as a *route function* decorated with
`@router.get/post/patch/put/delete(...)` inside one of the files under `app/api/routes/`.
Each route function's parameters are FastAPI **dependencies** (`Depends(...)`) — this is how
the database session, the current authenticated user, role checks, and service objects are
all supplied to a route without it constructing them itself.

**How the application starts.** `app/main.py` imports `app.api.router.api_router` (the
combined router) and `app.core.config.settings` (configuration), builds
`app = FastAPI(title=..., description=..., version=...)`, and calls
`app.include_router(api_router)`. That is the entire startup wiring — there is no
`@app.on_event("startup")` hook, no lifespan context manager. See Section 3 for what
"starting" actually does step by step.

**How routers are registered.** `app/api/router.py` creates one `api_router = APIRouter()`
and calls `api_router.include_router(...)` once per route module, in this exact order:
`health`, `auth`, `categories`, `departments`, `priorities`, `users`,
`tickets.flat_router` (the `/ticket-new` and `/all-tickets` endpoints — deliberately *not*
nested under `/tickets`), `tickets.router` (everything else under `/tickets/...`),
`attachments`. `app/main.py` then mounts this one combined router with a single
`app.include_router(api_router)` call.

**How requests move through the backend.**

```
Client / React frontend
    │  HTTP request (JSON or multipart), Authorization: Bearer <access token>
    ▼
FastAPI routing (app/api/router.py → the matching app/api/routes/*.py function)
    │
    ▼
Dependencies resolve, in declaration order (app/dependencies/*.py):
    - get_db()                     → opens a SQLAlchemy Session
    - get_current_user() /
      get_current_active_user()    → decodes the JWT, loads the User row
    - require_roles(...) or
      get_viewable_ticket()        → 401 / 403 if not authenticated / not allowed
    - get_<x>_service()             → builds the Service object for this route
    ▼
Pydantic request-body validation (the route's `payload: SomeCreate` parameter)
    │  422 raised automatically here if the JSON is invalid/missing fields
    ▼
Route function body (thin — a few lines) calls into a Service method
    ▼
Service (app/services/*.py) — business rules, ownership/role logic beyond
authentication, raises plain-Python domain exceptions (e.g. TicketNotFoundError)
    ▼
Repository (app/repositories/*.py) — the only layer that builds SQLAlchemy
`select()`/`insert` statements and touches the Session directly
    ▼
SQLAlchemy Core/ORM → pyodbc → SQL Server
    ▼
Service commits the transaction (`db.commit()`) and returns ORM model objects
    ▼
Route catches any domain exception and turns it into `HTTPException(status, detail)`
    ▼
Pydantic response schema (`response_model=...`) serializes the ORM object to JSON,
excluding anything not declared on the schema (e.g. password_hash)
    ▼
FastAPI returns the JSON response
    ▼
Client / React frontend receives the response
```

This exact flow — dependencies → validation → service → repository → DB → response schema
— is enforced by convention across every route in the project; it is described precisely in
service docstrings (e.g. `app/services/ticket_service.py`, `app/services/category_service.py`)
as "routes stay thin" and "repositories only flush, services own the transaction boundary."

**Main folders and their responsibility** (all under `backend/`):

| Folder | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI app and mounts the router. |
| `app/api/` | HTTP layer: `router.py` (top-level router) + `routes/*.py` (one file per resource: the actual `@router.get/post/...` endpoint functions). |
| `app/core/` | Cross-cutting infrastructure: `config.py` (settings/env), `security.py` (password hashing, JWT). |
| `app/db/` | `database.py` — the SQLAlchemy engine, session factory, and declarative `Base`. |
| `app/models/` | SQLAlchemy ORM model classes — one file per database table, plus `enums.py` and `mixins.py`. |
| `app/schemas/` | Pydantic v2 request/response models — one file per resource, plus `response.py` (the shared `{data, msg}` envelope). |
| `app/repositories/` | Persistence-only classes: build queries, `add`/`flush`/`delete` — never call `commit()`. |
| `app/services/` | Business logic: ownership rules, uniqueness rules, status workflow, transaction boundaries (`commit()`/`rollback()`), and the custom exceptions routes translate into HTTP errors. |
| `app/dependencies/` | FastAPI `Depends()` providers: wires `get_db` → repository → service, plus authentication/authorization dependencies. |
| `app/scripts/` | One-off maintenance scripts run with `python -m app.scripts.<name>` (currently `seed_initial_data.py`). |
| `scripts/` | Dev-only helper scripts *outside* the `app` package (`create_demo_users.py`) — not part of the deployable app. |
| `alembic/` | Database migration scripts (`versions/`) and Alembic's environment script (`env.py`). |
| `storage/attachments/` | Where uploaded ticket attachment files actually live on disk. |
| `tests/` | The `pytest` suite: `conftest.py` (fixtures/fakes) + one `test_*.py` file per feature area. |

---

## 2. Project structure — file by file

### `app/main.py`
Creates the one `FastAPI` app instance and includes `api_router`. Also defines a single
extra route, `GET /` (`root()`), returning `{"message": "Welcome to ITOnIT!"}` — a plain
liveness/landing endpoint, separate from `GET /health`. Used by: `uvicorn app.main:app`
(the ASGI entrypoint), and imported by every test via `tests/conftest.py`
(`from app.main import app`).

### `app/api/router.py`
Defines `api_router` and calls `include_router()` for every route module. This is the single
place new resource routers get registered. Used by: `app/main.py` only.

### `app/api/routes/`
One file per resource, each exporting an `APIRouter` (see Section 11 for full endpoint
detail):
- `health.py` — `GET /health`, checks the DB with `SELECT 1`.
- `auth.py` — `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`.
- `categories.py` — full CRUD for ticket categories.
- `departments.py` — CRUD-minus-delete for departments.
- `priorities.py` — CRUD-minus-delete for priorities.
- `locations.py` — CRUD-minus-delete for locations, plus `is_active` deactivation; write
  endpoints are Administrator-only (stricter than departments/priorities, which also allow
  Manager).
- `users.py` — user management + password endpoints.
- `tickets.py` — defines **two** routers: `router` (prefix `/tickets`, individual-ticket and
  sub-resource endpoints) and `flat_router` (no prefix — `POST /ticket-new`,
  `GET /all-tickets`; kept out of the `/tickets` prefix deliberately, see Section 11).
- `attachments.py` — its own router (`prefix="/tickets/{ticket_id}/attachments"`), separated
  from `tickets.py` because multipart upload and binary download responses are different
  enough concerns to warrant their own file (stated directly in the file's own comment).

### `app/core/config.py`
Defines `Settings(BaseSettings)` (pydantic-settings) and the module-level singleton
`settings = get_settings()`. See Section 4 for every field.

### `app/core/security.py`
All password hashing and JWT logic lives here and only here: `hash_password`,
`verify_password`, `create_access_token`, `create_refresh_token`, `decode_access_token`,
`decode_refresh_token`. Used by `app/services/auth_service.py`,
`app/dependencies/auth.py`, and `app/services/user_service.py` (for password changes).

### `app/db/database.py`
`build_connection_url()`, `engine`, `SessionLocal`, `Base`. See Section 5.

### `app/models/`
One SQLAlchemy model class per table: `role.py`, `user.py`, `department.py`, `priority.py`,
`category.py`, `ticket.py`, `comment.py`, `attachment.py`, `ticket_history.py`, plus
`enums.py` (`TicketStatus`) and `mixins.py` (`CreatedAtMixin`, `TimestampMixin`).
`app/models/__init__.py` imports every model so that `Base.metadata` knows about all of them
— this is required both for Alembic autogeneration (Section 6) and for
`sqlalchemy.orm.configure_mappers()` to succeed. See Section 7 for full detail.

### `app/schemas/`
Pydantic request/response models, one file per resource, plus `response.py`
(`DataResponse[T]`, the `{data, msg}` envelope used by newer endpoints) and `health.py`.
See Section 8.

### `app/services/`
Exists — one file per resource: `auth_service.py`, `user_service.py`,
`department_service.py`, `priority_service.py`, `category_service.py`, `ticket_service.py`,
`comment_service.py`, `attachment_service.py`, `history_service.py`, `storage_service.py`.
Every service class follows the same constructor pattern (the "injectable-with-real-default"
pattern, visible in every service, e.g. `TicketService.__init__`):

```python
def __init__(self, db, ticket_repository: TicketRepository | None = None, ...):
    self._ticket_repository = ticket_repository if ticket_repository is not None else TicketRepository(db)
```

This lets tests substitute an in-memory fake repository without touching a real database,
while production code (via the `get_<x>_service` dependency) always gets the real one.

### `app/repositories/`
Exists — `base.py` (`BaseRepository[ModelType]`, generic CRUD: `get_by_id`, `get_all`,
`create`, `update`, `delete`, `flush`, `refresh` — **no `commit()`**) plus one subclass per
resource. Several repositories override `get_by_id`/add list methods to eager-load
relationships with `selectinload(...)` specifically to avoid N+1 queries when a response
schema needs a nested object (e.g. `TicketRepository.get_by_id` eager-loads `category`,
`priority`, `created_by`, `assigned_technician`; `UserRepository.get_by_id` eager-loads
`role` and `department`).

### `app/dependencies/`
Exists — one file per resource pairing a `get_<x>_repository` and `get_<x>_service`
provider, plus `database.py` (`get_db`), `auth.py` (authentication/authorization), and
`ticket.py` (`get_viewable_ticket`, the shared ticket-ownership gate reused by every
`/tickets/{id}/...` sub-resource route). `app/dependencies/__init__.py` re-exports the ones
routes actually import, e.g. `from app.dependencies import get_ticket_service, require_roles`.

### `alembic/` (migrations)
`env.py` configures Alembic to target the real app database and compare against
`Base.metadata`; `versions/` holds three migration scripts in order:
`42ac9b9a44ba_initial_schema.py` → `496ee3278515_add_departments_and_user_profile_fields.py`
→ `b8c5e972dfbf_add_priorities_table_and_migrate_ticket_.py`. See Section 6.

### `storage/attachments/`
The real folder on disk where uploaded files are written by `StorageService.save()`. Its
path comes from `settings.ATTACHMENT_STORAGE_PATH` (default `storage/attachments`, relative
to the process's working directory, i.e. `backend/`). Contains a `.gitkeep` placeholder plus
whatever files have actually been uploaded (one real file, `36599e1c9f0e4586b2e23607cf45cbb3.png`,
was present at inspection time).

### `tests/`
`conftest.py` (fixtures + in-memory fakes, shared by every test file) plus one `test_*.py`
per feature. See Section 21.

---

## 3. Application startup flow

Running `python -m uvicorn app.main:app --reload` from `backend/` does, in order:

1. **Python imports `app.main`.** This is a plain module import, so Python executes
   `app/main.py` top to bottom.
2. That triggers `from app.api.router import api_router`, which imports
   `app/api/router.py`, which imports every route module in `app/api/routes/`. Each of those
   route modules imports its dependencies (`app/dependencies/*.py`), which import their
   services (`app/services/*.py`), which import their repositories (`app/repositories/*.py`)
   and models (`app/models/*.py`).
3. **Configuration loads.** The first time anything imports `app.core.config`, module-level
   code runs: `settings = get_settings()` constructs a `Settings()` instance, which — because
   `Settings` subclasses pydantic-settings' `BaseSettings` with
   `SettingsConfigDict(env_file=".env", ...)` — reads `backend/.env` (if present) and the
   real OS environment, and **raises a `pydantic.ValidationError` immediately if a required
   field (`DATABASE_SERVER`, `DATABASE_NAME`, `SECRET_KEY`) is missing.** This means a
   misconfigured `.env` file causes the import itself to fail — the server never gets to the
   point of listening for connections.
4. **The database connection is prepared, but not opened.** Importing `app.db.database` runs
   `engine = create_engine(build_connection_url())`. `create_engine()` only configures a
   connection pool — SQLAlchemy's own documentation (and the comment directly above this
   line in the code) states it does not actually connect to SQL Server until a session
   executes a query. So the app can start even if SQL Server is unreachable; the very first
   real query (e.g. the first `GET /health` call, or the first authenticated request) is
   where a connection failure would actually surface.
5. **`app = FastAPI(title=settings.APP_NAME, description=..., version=settings.APP_VERSION)`
   runs.** This constructs the ASGI application object and, as a side effect of FastAPI's
   own internals, prepares the machinery that will later generate the OpenAPI schema.
6. **`app.include_router(api_router)` runs.** Every route registered via
   `api_router.include_router(...)` in step 2 is now attached to `app`, with its path,
   HTTP method, security scheme, and Pydantic response model recorded.
7. **`uvicorn` starts serving.** It binds to a socket (default `127.0.0.1:8000` unless
   `--host`/`--port` are given) and begins accepting HTTP connections, running the ASGI
   callable (`app`) once per request. `--reload` additionally watches the source files and
   restarts this whole process on any change.
8. **Swagger becomes available.** Because FastAPI auto-generates an OpenAPI schema from every
   route's declared parameters, dependencies, and `response_model`, `GET /docs` (Swagger UI)
   and `GET /openapi.json` are live as soon as the app object exists — no separate step is
   needed. See Section 24.
9. **A request reaching the server** goes through exactly the flow diagrammed in Section 1:
   FastAPI's router matches method+path, resolves every `Depends()` in the route's signature
   (opening a DB session via `get_db`, authenticating via `get_current_user`, etc.), validates
   the request body against the route's Pydantic schema, runs the route function, and returns
   its result serialized against `response_model`.

---

## 4. Configuration and environment variables

**Settings class:** `app.core.config.Settings` in `app/core/config.py`, a
`pydantic_settings.BaseSettings` subclass. Its `model_config` is:

```python
model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")
```

`env_file=".env"` means pydantic-settings loads `backend/.env` (working-directory-relative)
automatically; `case_sensitive=True` means the environment variable names must match the
field names exactly (e.g. `DATABASE_SERVER`, not `database_server`); `extra="ignore"` means
unrecognized keys in `.env` are silently ignored rather than raising an error.

**Every field, exactly as declared in `app/core/config.py`:**

| Field | Type | Default | Required? |
|---|---|---|---|
| `APP_NAME` | str | `"ITOnIT API"` | no |
| `APP_VERSION` | str | `"1.0.0"` | no |
| `DATABASE_SERVER` | str | — | **yes** |
| `DATABASE_NAME` | str | — | **yes** |
| `DATABASE_DRIVER` | str | `"ODBC Driver 17 for SQL Server"` | no |
| `DATABASE_USERNAME` | str \| None | `None` | no |
| `DATABASE_PASSWORD` | str \| None | `None` | no |
| `SECRET_KEY` | str | — | **yes** |
| `ALGORITHM` | str | `"HS256"` | no |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `30` | no |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | int | `10080` (7 days) | no |
| `INITIAL_ADMIN_EMAIL` / `_PASSWORD` / `_FIRST_NAME` / `_LAST_NAME` | str \| None | `None` | no (only used by `app.scripts.seed_initial_data`) |
| `ATTACHMENT_STORAGE_PATH` | str | `"storage/attachments"` | no |
| `MAX_ATTACHMENT_SIZE_BYTES` | int | `10485760` (10 MB) | no |

`backend/.env.example` documents every one of these with the same names and shows the
default/expected shape (e.g. `DATABASE_SERVER=localhost\SQLEXPRESS`).

**How the SQL Server connection string is built:** `app/db/database.py`,
`build_connection_url()`. If `DATABASE_USERNAME` and `DATABASE_PASSWORD` are both set, it
builds `mssql+pyodbc://user:pass@server/db?driver=<url-encoded driver>`. If either is
missing, it instead appends `&trusted_connection=yes` and omits credentials — i.e. it falls
back to **Windows Trusted Connection** authentication. Both the username/password and the
driver name are passed through `urllib.parse.quote_plus` to safely URL-encode special
characters (e.g. spaces in `"ODBC Driver 17 for SQL Server"`).

**How JWT settings are loaded:** `app/core/security.py` reads `settings.SECRET_KEY`,
`settings.ALGORITHM`, `settings.ACCESS_TOKEN_EXPIRE_MINUTES`, and
`settings.REFRESH_TOKEN_EXPIRE_MINUTES` directly at token-creation/decode time (not cached
elsewhere) — so changing `.env` and restarting the process changes token behavior
immediately.

**How file-storage settings are loaded:** `app/services/storage_service.py`'s
`StorageService.__init__` reads `settings.ATTACHMENT_STORAGE_PATH` as its default base path;
`app/services/attachment_service.py` reads `settings.MAX_ATTACHMENT_SIZE_BYTES` directly
inside `upload_attachment()`.

**Why secrets should not be committed to Git.** `backend/.env` is listed in the repo's
top-level `.gitignore` (`.env` and `backend/.env` both appear there), so a developer's real
`SECRET_KEY` and database credentials are never tracked by Git. Only `.env.example` — which
contains placeholder values like `SECRET_KEY=change-me-to-a-random-secret` and blank
credential fields — is committed. This matters because `SECRET_KEY` is the value that signs
every JWT; anyone with it can forge valid access/refresh tokens for any user.

---

## 5. Database architecture

**How SQLAlchemy connects to SQL Server.** Via `pyodbc` (dialect `mssql+pyodbc`), configured
in `app/db/database.py`. The connection URL is built by `build_connection_url()` (Section 4)
and handed to `sqlalchemy.create_engine()`.

**The engine.** `engine = create_engine(build_connection_url())` — a module-level singleton
created once, when `app.db.database` is first imported. It owns the connection pool; it does
not itself represent one connection.

**The session factory.** `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
`autocommit=False` means nothing is written to the database until code explicitly calls
`.commit()`. `autoflush=False` means pending changes are not automatically sent to the
database before every query — they are only sent on an explicit `.flush()` or `.commit()`
(or when a query needs to see them).

**What a database session is.** One `Session` object (an instance produced by calling
`SessionLocal()`) represents a single logical unit-of-work: a set of queries and pending
changes that will eventually be committed or rolled back together. In this codebase, exactly
one `Session` is created per HTTP request (see next point).

**How `get_db` works.** `app/dependencies/database.py`:

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

This is a FastAPI *yield-dependency*. FastAPI runs the code before `yield` when the
dependency is first requested for a request, hands the yielded `Session` to every route
parameter/dependency that asked for `Depends(get_db)`, and — because FastAPI caches a
dependency's result per request — every repository built during that one request shares the
exact same `Session` object. After the route function returns (successfully or with an
exception), FastAPI resumes this generator past `yield`, running the `finally: db.close()`.

**When transactions are committed.** Never inside a repository. Every repository method in
`app/repositories/` calls at most `self.db.add(...)`, `self.flush()`, or `self.db.delete(...)`
— never `self.db.commit()` (`BaseRepository` has no `commit` method at all). Commit happens
inside the **service** layer, at the end of whichever method represents one complete business
operation — e.g. `TicketService._persist_new_ticket` calls `self._db.commit()` right after
creating the ticket row and its "ticket_created" history row, so both succeed or fail
together; `UserService.update_user` commits once after all field changes are applied.

**When rollback happens.** Explicitly, inside a service's `except` block, whenever a database
constraint violation is caught as defense-in-depth against a race condition — e.g.
`CategoryService.create_category` catches `IntegrityError`, calls `self._db.rollback()`, and
re-raises as its own `CategoryNameConflictError`; `TicketService._persist_new_ticket` does the
same for a duplicate `ticket_number` and retries (Section 13).

**When the session is closed.** Always in `get_db`'s `finally` block, once per request,
regardless of success or failure.

**How SQLAlchemy models become database tables.** Every model class in `app/models/`
inherits from `app.db.database.Base` (a `DeclarativeBase` subclass) and declares
`__tablename__` plus `Mapped[...]`/`mapped_column(...)` attributes. `Base.metadata` collects
every subclass's table definition. Two different things then turn that metadata into real SQL
Server tables: (a) Alembic migrations, applied with `alembic upgrade head` — this is how the
real database gets its schema (Section 6); SQLAlchemy's own `Base.metadata.create_all()` is
never called anywhere in this codebase, confirmed by its absence from `app/main.py` and every
script.

**Role of `Base`.** The shared declarative base every model inherits from — it is what lets
Alembic's `env.py` compare "what the models say the schema should be" (`Base.metadata`)
against "what the real database's schema actually is."

**Role of `engine`.** The connection-pool owner; every `Session` ultimately borrows a raw
DB-API connection from it.

**Role of `SessionLocal`.** The factory that produces new `Session` objects, one per request.

**Relationships.** Declared with SQLAlchemy's `relationship(back_populates=...)`, always
paired on both sides (e.g. `Ticket.category` / `Category.tickets`). Two relationships on
`Ticket` (`created_by`, `assigned_technician`) both point at `User`, so they must — and do —
disambiguate with an explicit `foreign_keys=[...]` argument, since SQLAlchemy cannot infer
which FK column each relationship means when there are two FKs to the same table.

**Foreign keys.** Declared with `mapped_column(ForeignKey("<table>.<column>"))`, e.g.
`Ticket.priority_id: Mapped[int] = mapped_column(ForeignKey("priorities.id"), nullable=False)`.
Confirmed against the live database (via SQLAlchemy `inspect()`), every FK in the model layer
exists as a real FK constraint in SQL Server.

**Unique constraints.** Declared with `unique=True` on the column (e.g.
`User.username`, `User.email`, `Category.name`, `Department.title`, `Priority.title`,
`Location.title`, `Ticket.ticket_number`, `Role.name`) — SQLAlchemy/Alembic turns these into
real unique indexes, confirmed in the live database inspection (Section 5 of the DB schema
section below).

**Indexes.** No column is given an explicit `Index(...)`/`index=True` beyond what
`unique=True` and `primary_key=True` already create automatically — **confirmed directly
against the live database** (via `sqlalchemy.inspect()`): every foreign-key column
(`tickets.category_id/priority_id/location_id/created_by_user_id/assigned_technician_id`,
`comments.ticket_id/author_user_id`, `attachments.ticket_id/uploaded_by_user_id`,
`ticket_history.ticket_id/changed_by_user_id`, `users.role_id/department_id`) has **no
index at all**. This is the single highest-value database improvement available: every
ownership-scoped or filtered query (an Employee's own tickets, a technician's assigned
tickets, `GET /all-tickets` filters, a ticket's comments/attachments/history) currently does
a full table scan on these columns. Harmless at the current data volume; worth adding before
this ever runs with real production-scale data. `docs/database-design.md` (the original
design document, now partially outdated — see Section 22 for the discrepancies) already
anticipated this and lists candidate columns for future indexing.

**Enums.** `TicketStatus` (`app/models/enums.py`) is a Python `str, enum.Enum` with six
members. It's mapped to a SQL Server column via SQLAlchemy's `Enum(...)` type with
`native_enum=False` — meaning SQL Server does not use its own (nonexistent) native enum type;
instead SQLAlchemy stores it as a `VARCHAR` and adds a `CHECK` constraint
(`create_constraint=True`, named `ck_tickets_status`) restricting the column to the six valid
string values. The old `TicketPriority` enum has been **removed entirely** — priority is now
a foreign key into the `priorities` table (Section 7), not an enum.

**Timestamps.** `app/models/mixins.py` defines `CreatedAtMixin` (`created_at`, server-default
`func.now()`) and `TimestampMixin(CreatedAtMixin)` (adds `updated_at`, server-default
`func.now()` **and** `onupdate=func.now()` — so `updated_at` is automatically refreshed by
SQLAlchemy on every `UPDATE` it issues for that row, with no application code needing to set
it). `User`, `Ticket`, `Department`, `Priority`, and `Location` use `TimestampMixin`;
`Category`, `Comment`, `Attachment`, and `TicketHistory` use only `CreatedAtMixin` (`Comment`
additionally has its own nullable `updated_at` column, set manually by
`CommentService.update_comment`, since edits are the exception rather than the rule for a
comment).

**`is_active` / soft delete.** `User.is_active`, `Category.is_active`, and
`Location.is_active` (all boolean, default `True`) exist. **Confirmed from the code**:
`User.is_active` is actively enforced — `get_current_active_user` (Section 9) rejects
inactive users on every authenticated request, and `AuthService.authenticate` rejects login
for an inactive user. `Location.is_active` is also actively enforced —
`TicketService._get_location_or_raise` rejects setting a ticket's `location_id` to a
deactivated location. **`Category.is_active` is not currently read or written anywhere in
the service/route layer** — grepping `app/services/category_service.py` and
`app/api/routes/categories.py` shows no reference to it; only the migration/model declares
it. This is a genuine, confirmed inconsistency: `Location` shows the intended pattern
(deactivate instead of delete, enforced at the point of new selection), but `Category` has
the identical flag sitting completely inert, and `Department`/`Priority` have no such flag
at all despite having the same lifecycle need. See Section 22.
There is no `deleted_at` or soft-delete flag on `Ticket`, `Comment`, `Attachment`, or
`Department`/`Priority` (which instead simply have no delete endpoint at all — see Section
11) — deleting a `Ticket` (via `DELETE /tickets/{id}`) is a real `DELETE`, and its
`cascade="all, delete-orphan"` relationships (`comments`, `attachments`,
`history`) mean deleting a ticket permanently deletes all of its comments, attachments, and
history *rows* too (confirmed in `app/models/ticket.py`). Note that this cascade is
implemented at the **SQLAlchemy ORM level**, not as an `ON DELETE CASCADE` on the underlying
FK constraints (none of them declare `ondelete=`) — it works correctly for every deletion the
app actually performs (always through `TicketService.delete_ticket`), but a raw SQL delete of
a ticket row, bypassing the ORM, would not cascade at the database level. `TicketService
.delete_ticket` also deletes the physical attachment *files* from disk before returning — a
gap that existed until a recent review found it (deleting a ticket previously left orphaned
files on disk indefinitely; fixed by capturing each attachment's `file_path` before the
cascade delete and removing it from disk afterward, mirroring `AttachmentService
.delete_attachment`'s existing ordering).

---

## 6. Alembic and migrations

**Why Alembic is used.** SQL Server has no built-in mechanism for versioned, repeatable
schema changes. Alembic lets every schema change be written as Python code (a "migration"),
checked into Git, applied in a defined order, and — critically — reversed
(`downgrade()`) if needed. `docs/database-design.md` states explicitly: *"Database tables
will not be created manually in SQL Server Management Studio (SSMS). All tables will be
created and versioned later through Alembic migrations."*

**How Alembic reads SQLAlchemy metadata.** `alembic/env.py` does
`from app.db.database import Base, build_connection_url` and
`from app.models import *` (the `import *` is what actually registers every model class on
`Base.metadata` — importing only `Base` would make Alembic see an empty schema, as the
file's own comment states), then sets `target_metadata = Base.metadata`. When you run
`alembic revision --autogenerate`, Alembic connects to the real database, introspects its
current schema, and diffs it against `target_metadata` to produce the migration script.

**What `env.py` does, step by step:**
1. Imports `Base` and every model (so `Base.metadata` is complete).
2. Reads `alembic.ini`'s logging config.
3. **Overrides** the connection URL: `config.set_main_option("sqlalchemy.url", build_connection_url())` —
   meaning Alembic always targets the exact same database the running FastAPI app would
   connect to (built from `.env` via `app.core.config.settings`), never a separately
   configured URL sitting in `alembic.ini`.
4. Defines `run_migrations_offline()` (emit SQL without a live DB connection — not used in
   this project's normal workflow) and `run_migrations_online()` (open a real connection with
   `NullPool` and run migrations inside a transaction).
5. Dispatches to online or offline mode based on `context.is_offline_mode()`.

**How migration files are generated.** `alembic revision --autogenerate -m "<message>"` (run
from `backend/`, so it picks up `alembic.ini` and imports `app.models` correctly) produces a
new file under `alembic/versions/`, pre-filled with `op.create_table`/`op.add_column`/etc.
calls that Alembic inferred from the model diff — always reviewed and adjusted by a human
before being trusted (the auto-generated comment `# ### commands auto generated by Alembic -
please adjust! ###` appears in `42ac9b9a44ba_initial_schema.py`). The two later migrations
(`496ee3278515...` and `b8c5e972dfbf...`) are hand-written/hand-adjusted beyond the
autogenerate skeleton — they contain manual `op.execute(...)` data-migration SQL (backfilling
`username`, converting the old free-text `department` column into real `Department` rows,
converting the old `priority` enum column into `priority_id` foreign keys) that Alembic
cannot infer automatically.

**What `alembic upgrade head` does.** Runs every migration between the database's current
recorded revision (tracked in a special `alembic_version` table — confirmed present in the
live database) and the latest ("head") revision, in dependency order (each migration declares
its `down_revision`, forming a chain:
`None → 42ac9b9a44ba → 496ee3278515 → b8c5e972dfbf`), each inside its own transaction.

**Why database changes should go through migrations instead of manual SQL Server edits.**
A manual `ALTER TABLE` in SSMS is invisible to Alembic's `alembic_version` tracking and to
Git — it can't be reproduced on another developer's machine, can't be reviewed in a pull
request, and (as demonstrated by `496ee3278515`'s careful data-preserving column rename) a
raw schema edit risks silently losing or corrupting existing data that a proper migration
script handles deliberately.

**Typical commands used in this project** (all run from `backend/`):

```bash
alembic upgrade head          # apply all pending migrations
alembic current               # show the DB's current revision
alembic heads                 # show the latest available revision
alembic check                 # verify models match the DB with no drift
alembic revision --autogenerate -m "message"   # generate a new migration
alembic downgrade -1          # revert the most recent migration
```

---

## 7. Database models and relationships

Every model below inherits `app.db.database.Base`; file paths are under `app/models/`.

### `Role` (`role.py`)
**Purpose:** the permission level assigned to a user (Employee, Technician, Manager,
Administrator). **Columns:** `id` (PK), `name` (String(30), unique, required), `description`
(String(255), nullable). **Relationships:** `users` — one `Role` has many `User`s
(`back_populates="role"`). No timestamps (roles are static reference data).

### `User` (`user.py`)
**Purpose:** every person who logs in — employee, technician, manager, or administrator.
**Columns:** `id` (PK), `username` (String(50), unique, required — the login identifier),
`first_name`, `last_name` (String(100), required), `email` (String(255), unique, required),
`password_hash` (String(255), required — **never the plaintext password**), `phone_number`
(String(30), nullable), `department_id` (FK → `departments.id`, **nullable** — a user may
have no department), `role_id` (FK → `roles.id`, required), `theme` (String(20), nullable,
Python-side default `"light"`), `is_active` (Boolean, required, default `True`).
Inherits `TimestampMixin` → `created_at`, `updated_at`. **Relationships:** `role` (many
`User` → one `Role`), `department` (many `User` → one, optional, `Department`),
`created_tickets` (one `User` → many `Ticket`, via `Ticket.created_by_user_id`),
`assigned_tickets` (one `User` → many `Ticket`, via `Ticket.assigned_technician_id`),
`comments`, `attachments`, `history_entries`.

### `Department` (`department.py`)
**Purpose:** an organizational department a user may belong to (e.g. IT, HR). **Columns:**
`id` (PK), `title` (String(100), unique, required). `TimestampMixin`.
**Relationships:** `users` — one `Department` has many `User`s.

### `Priority` (`priority.py`)
**Purpose:** a ticket priority level (Low/Medium/High/Critical by default, but now a real,
manageable table rather than a hard-coded enum — the model's own docstring states this is
exactly why it replaced the old `TicketPriority` enum). **Columns:** `id` (PK), `title`
(String(50), unique, required). `TimestampMixin`. **Relationships:** `tickets` — one
`Priority` has many `Ticket`s.

### `Category` (`category.py`)
**Purpose:** classifies a ticket by issue type (Hardware, Software, Network, ...).
**Columns:** `id` (PK), `name` (String(100), unique, required), `description` (String(255),
nullable), `is_active` (Boolean, default `True` — **confirmed still unused**: declared on the
model but never read or written by any schema/service/route; see Section 22's consistency
findings). `CreatedAtMixin` only (no `updated_at`).
**Relationships:** `tickets` — one `Category` has many `Ticket`s.

### `Location` (`location.py`)
**Purpose:** a predefined physical location a ticket can be reported from (e.g. "Head Office
- Floor 2 - Desk 18"), chosen from a managed list instead of typed freely - replaces the
former free-text `Ticket.location` string column. **Columns:** `id` (PK), `title`
(String(100), unique, required), `is_active` (Boolean, default `True` - **and, unlike
Category's, this flag is actually enforced**: `TicketService._get_location_or_raise` rejects
any attempt to set a ticket's `location_id` to a deactivated location, both on
`POST /ticket-new` and `PATCH /tickets/{id}`). `TimestampMixin`. **Relationships:** `tickets`
— one `Location` has many `Ticket`s. There is deliberately no delete method/endpoint —
retiring a location is done via `PATCH /locations/{id}` with `{"is_active": false}`, so a
ticket that already references one is never broken by its retirement.

### `Ticket` (`ticket.py`)
**Purpose:** the central entity — one IT support request, tracked start to finish.
**Columns:** `id` (PK), `ticket_number` (String(30), unique, required — the public,
human-readable ID), `title` (String(200), required), `description` (Text, required),
`location_id` (FK → `locations.id`, **nullable** — where the issue is physically located; a
ticket may have no location, and, once set, may be explicitly cleared back to `null` via
`PATCH /tickets/{id}`), `status` (`TicketStatus` enum, required — see Section 14),
`priority_id` (FK → `priorities.id`, required), `category_id` (FK → `categories.id`,
required), `created_by_user_id` (FK → `users.id`, required — who reported it),
`assigned_technician_id` (FK → `users.id`, **nullable** — unassigned until a Manager/Admin
assigns someone), `resolved_at` / `closed_at` (DateTime, nullable — set only when the ticket
reaches those statuses). `TimestampMixin`. **Relationships:** `category`, `priority`,
`location`, `created_by`, `assigned_technician` (all many-to-one), plus `comments`,
`attachments`, `history` — all three declared with `cascade="all, delete-orphan"`, meaning
deleting a `Ticket` deletes its comments/attachments/history *database rows* with it (see
Section 22 for the caveat that the physical attachment *files* needed an explicit fix to be
cleaned up too - `TicketService.delete_ticket` now does this).

### `Comment` (`comment.py`)
**Purpose:** one message posted on a ticket. **Columns:** `id` (PK), `ticket_id`
(FK → `tickets.id`, required), `author_user_id` (FK → `users.id`, required), `content`
(Text, required), `updated_at` (DateTime, nullable — only set if the comment is edited).
`CreatedAtMixin`. **Relationships:** `ticket` (many-to-one), `author` (many-to-one, `User`).
A comment no longer has an `attachments` relationship - see `Attachment` below.

### `Attachment` (`attachment.py`)
**Purpose:** metadata for one uploaded file — the file's *bytes* live on disk, not in SQL
Server (model docstring states this directly). **Columns:** `id` (PK), `ticket_id`
(FK → `tickets.id`, required), `uploaded_by_user_id` (FK → `users.id`, required),
`original_filename` (String(255), required — the name the user uploaded it as),
`stored_filename` (String(255), required — the random, server-generated name it's actually
saved as on disk), `file_path` (String(500), required — in the current implementation this
is always identical to `stored_filename`, a flat path relative to the storage root; see
Section 16), `content_type` (String(100), nullable), `file_size` (Integer, required).
`CreatedAtMixin`. **Relationships:** `ticket`, `uploaded_by`. An attachment belongs to
exactly one entity - its ticket - not optionally to a ticket *and* a comment; the model
previously had a nullable `comment_id`, which was removed (it was never actually set by any
code path) so that an attachment has a single, unambiguous owner.

### `TicketHistory` (`ticket_history.py`)
**Purpose:** one field-level audit record — who changed what field, from what value to what
value, and when. **Columns:** `id` (PK), `ticket_id` (FK → `tickets.id`, required),
`changed_by_user_id` (FK → `users.id`, required), `field_name` (String(50), required),
`old_value` / `new_value` (String(255), nullable — both are free text, truncated to 255
characters by `HistoryService._truncate` before being stored, matching the column width).
`CreatedAtMixin`. **Relationships:** `ticket`, `changed_by` (`User`).

### Overall relationship flow

```
Role
  → has many Users

Department
  → has many Users (optional membership — department_id is nullable)

User
  → creates many Tickets (created_by_user_id)
  → may be assigned many Tickets as technician (assigned_technician_id, nullable)
  → writes many Comments
  → uploads many Attachments
  → performs many TicketHistory changes

Category
  → classifies many Tickets

Priority
  → is the priority level of many Tickets

Location
  → is the reported location of many Tickets (nullable, deactivatable)

Ticket
  → belongs to one Category
  → belongs to one Priority
  → optionally belongs to one Location
  → was created by one User
  → may be assigned to one User as technician (nullable)
  → has many Comments        (cascade: deleted with the ticket)
  → has many Attachments     (cascade: deleted with the ticket, files included)
  → has many TicketHistory records  (cascade: deleted with the ticket)

Comment
  → belongs to one Ticket
  → was written by one User

Attachment
  → belongs to exactly one Ticket (its only owner)
  → was uploaded by one User
```

This matches (and, since the Milestone 9 changes, extends beyond) the relationships listed
in `docs/database-design.md` §10 — see Section 22 for exactly what has changed since that
document was written.

---

## 8. Pydantic schemas

**Why request/response schemas are separate from database models.** A SQLAlchemy model
(`app/models/user.py`'s `User`) represents *storage* — every column that exists in the table,
including `password_hash`. A Pydantic schema (`app/schemas/user.py`'s `UserResponse`)
represents *the shape of one specific HTTP message* — only the fields that message should
contain. Keeping them separate means the database can have a column (`password_hash`) that
literally no response schema in the entire codebase declares, so it is structurally
impossible for a route to leak it by accident — not because someone remembered to exclude
it, but because the response model doesn't have the field to begin with.

**How Pydantic validates incoming JSON.** Every route that accepts a body declares a
parameter typed as a `Create`/`Update`/request schema (e.g.
`def create_user(payload: UserCreate, ...)`). FastAPI parses the request JSON against that
model *before* the route function body runs; a type mismatch, a missing required field, or a
failed `@field_validator` (many schemas define one to strip whitespace and reject blank
strings, e.g. `CategoryBase._strip_name` in `app/schemas/category.py`) all raise a
`RequestValidationError`, which FastAPI's built-in handler turns into an **HTTP 422** with a
structured `detail` array — before any service or database code runs.

**How response schemas control returned data.** Every route declares `response_model=...`
(or its FastAPI-inferred equivalent, the function's `-> ReturnType` annotation). FastAPI
calls `SchemaClass.model_validate(orm_object)` (enabled by `model_config =
ConfigDict(from_attributes=True)` on every response schema — this is what lets Pydantic read
attributes off a SQLAlchemy object rather than requiring a dict) and serializes *only* the
fields the schema declares.

**How nested objects are returned.** A response schema can nest another schema as a field
type, and Pydantic recursively validates/serializes it. Example: `TicketResponse`
(`app/schemas/ticket.py`) declares `category: CategoryResponse`, `priority: PriorityResponse`,
`created_by: TicketUserSummary`, `assigned_technician: TicketUserSummary | None` — so a
single `GET /tickets/{id}` call returns the full category/priority/user objects inline,
without the client making three more requests. `TicketUserSummary` (also in
`app/schemas/ticket.py`) is a deliberately minimal user schema (`id`, `first_name`,
`last_name`, `email` only) reused everywhere a ticket needs to show *who* did something —
comments, attachments, and history all embed it too (`CommentResponse.author`,
`AttachmentResponse.uploaded_by`, `TicketHistoryResponse.performed_by`).

**How sensitive fields are excluded.** By omission, not by a special decorator: no response
schema anywhere in `app/schemas/` declares `password_hash`. `UserResponse`
(`app/schemas/user.py`) explicitly documents this in its own docstring: *"never returns
password/password_hash."*

### Schema groups, by resource (all in `app/schemas/`)

| Resource | File | Key classes |
|---|---|---|
| Authentication | `auth.py` | `LoginRequest` (`username`, `password`), `TokenResponse` (`access`, `refresh`, `token_type`), `RefreshRequest` (`refresh`), `RefreshResponse` (`access`, `token_type`), `TokenPayload` (internal — decoded JWT shape), `CurrentUserResponse` (for `GET /auth/me`) |
| Users | `user.py` | `UserCreate`, `UserUpdate` (all fields optional — partial patch), `PasswordChangeRequest`, `AdminPasswordSetRequest`, `UserResponse` (nests `DepartmentResponse`, resolves `role` from either a `Role` object or a plain string) |
| Departments | `department.py` | `DepartmentCreate`, `DepartmentUpdate`, `DepartmentResponse` |
| Priorities | `priority.py` | `PriorityCreate`, `PriorityUpdate`, `PriorityResponse` |
| Locations | `location.py` | `LocationCreate`, `LocationUpdate` (`title` and `is_active`, both optional), `LocationResponse` (includes `is_active`) |
| Categories | `category.py` | `CategoryCreate`, `CategoryUpdate` (full replacement, not partial), `CategoryResponse` |
| Tickets | `ticket.py` | `TicketContentBase` (shared validation for title/description/location_id/category_id/priority_id), `TicketNewCreate` (adds optional `requester_user_id`), `TicketPatch` (all optional — partial), `TicketAssign`, `TicketStatusUpdate`, `TicketResponse` (nests `LocationResponse | None`, `CategoryResponse`, `PriorityResponse`), `TicketUserSummary` |
| Comments | `comment.py` | `CommentContentBase`, `CommentCreate`, `CommentUpdate`, `CommentResponse` |
| Attachments | `attachment.py` | `AttachmentResponse` (no request schema — the request is raw multipart `UploadFile`, handled directly in the route, not via a Pydantic body model) |
| History | `history.py` | `TicketHistoryResponse` (uses `Field(validation_alias=...)` to rename the model's `field_name`/`changed_by`/`created_at` columns to the friendlier `action`/`performed_by`/`timestamp` in the API response, without touching the underlying model) |
| Response envelope | `response.py` | `DataResponse[T]` — generic `{data: T, msg: str}` wrapper (see Section 19) |
| Health | `health.py` | `HealthResponse` |

---

## 9. Authentication flow

**Full login process, step by step** (`POST /auth/login`, handled by `login()` in
`app/api/routes/auth.py`, delegating to `AuthService.login()` in
`app/services/auth_service.py`):

1. Client sends `POST /auth/login` with JSON `{"username": "...", "password": "..."}` —
   validated against `LoginRequest`. The field is named `username`, but see step 2.
2. `AuthService.authenticate(username, password)` calls
   `self._user_repository.get_by_username_or_email(username)`
   (`app/repositories/user.py`) — one query that matches **either** the `username` column
   **or** the `email` column (case-insensitively, via `func.lower(...)`). This is a
   deliberate design choice: `username` is the one documented login field, but existing
   email-based logins keep working because the lookup checks both — there is no second,
   separately-documented "login with email" field.
3. If no user is found, `AuthService` raises `InvalidCredentialsError` immediately — the
   route always returns the same 401 message regardless of whether the username doesn't
   exist or the password is wrong, so a caller cannot use the error to probe which accounts
   exist (stated directly in `InvalidCredentialsError`'s docstring).
4. If a user *is* found, the backend verifies the password:
   `verify_password(password, user.password_hash)` in `app/core/security.py`, which calls
   `pwdlib`'s Argon2 `PasswordHash.recommended().verify(plain_password, password_hash)`.
   A mismatch raises the same `InvalidCredentialsError`.
5. The backend checks `user.is_active` — if `False`, again `InvalidCredentialsError` (same
   generic message, for the same probing-resistance reason).
6. `AuthService.issue_tokens(user)` creates **both** tokens:
   `create_access_token(subject=user.id)` and `create_refresh_token(subject=user.id)`
   (`app/core/security.py`).
7. Both tokens, plus `"token_type": "bearer"`, are returned as `TokenResponse` — JSON
   `{"access": "...", "refresh": "...", "token_type": "bearer"}`.
8. The client stores both tokens and sends the access token on every subsequent request as
   `Authorization: Bearer <access token>`.
9. `app/dependencies/auth.py`'s `get_current_user` resolves that header via FastAPI's
   `HTTPBearer(auto_error=False)` security scheme, then calls
   `decode_access_token(credentials.credentials)`.
10. `decode_access_token` (`app/core/security.py`) verifies the JWT signature with
    `settings.SECRET_KEY`/`settings.ALGORITHM`, checks the `sub` claim is present, and checks
    the `"type"` claim equals `"access"` — rejecting the token (raising
    `jwt.InvalidTokenError`) if it's actually a refresh token.
11. `get_current_user` looks up the user by the decoded `sub` (the user's `id`) via
    `user_repository.get_by_id(user_id)`; if the token is malformed, expired, wrong-typed, or
    the user no longer exists, the same generic `_credentials_error()` (401) is raised.
12. `get_current_active_user` wraps `get_current_user` and additionally 401s if
    `current_user.is_active` is `False` — so deactivating a user immediately locks them out of
    every subsequent request, even with a still-unexpired access token.
13. The protected endpoint's route function now runs, with `current_user: User` available.

**Password hashing/verification.** Argon2, via `pwdlib.PasswordHash.recommended()`
(`app/core/security.py`). `hash_password(password)` never stores or logs the plaintext; only
`password_hash` is persisted. `verify_password` re-hashes the supplied plaintext (with the
stored hash's embedded salt/parameters) and compares — this is why plaintext passwords are
never stored: the hash function is one-way, and Argon2's built-in per-hash salt means two
users with the same password get different `password_hash` values.

**JWT payload.** Both access and refresh tokens carry: `sub` (the user's `id`, as a string),
`type` (`"access"` or `"refresh"`), `iat` (issued-at), `exp` (expiry). No other user data
(name, email, role) is embedded in the token — every request re-fetches the current `User`
row from the database via `get_by_id`, so role/active-status changes take effect on the very
next request, not just after the token expires.

**Token expiry.** Access tokens: `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (default 30 minutes).
Refresh tokens: `settings.REFRESH_TOKEN_EXPIRE_MINUTES` (default 10080 minutes = 7 days) —
deliberately much longer, since the whole point of a refresh token is to outlive the access
token (stated directly as a comment on the setting).

**Bearer authentication.** Implemented via FastAPI/Starlette's `HTTPBearer(auto_error=False)`
(`app/dependencies/auth.py`). `auto_error=False` is deliberate: FastAPI's default behavior
for a *missing* Authorization header is to raise its own 403; setting this to `False` lets
`get_current_user` instead raise the project's own consistent 401
(`WWW-Authenticate: Bearer`) for every authentication failure — missing header, malformed
token, expired token, or wrong-token-type.

**What happens with invalid or expired tokens.** `decode_access_token`/`decode_refresh_token`
raise a `jwt.PyJWTError` subclass (`ExpiredSignatureError` for expiry,
`DecodeError`/`InvalidTokenError` for a malformed or wrong-type token). `get_current_user`
catches `(jwt.PyJWTError, ValueError)` and turns any of them into the same 401.

### Refresh-token flow, in detail

`POST /auth/refresh` (`refresh()` in `app/api/routes/auth.py`, delegating to
`AuthService.refresh_access_token()`):

1. Client sends `{"refresh": "<refresh token>"}` (`RefreshRequest`).
2. `decode_refresh_token(refresh_token)` verifies the signature and checks `"type" ==
   "refresh"` — **an access token presented here is rejected**, because it fails this type
   check (confirmed directly by `tests/test_auth.py::test_refresh_rejects_an_access_token`).
3. The `sub` claim is parsed back to a user id; `user_repository.get_by_id(user_id)` is
   looked up; if the user no longer exists or `is_active` is `False`, the whole thing raises
   `InvalidRefreshTokenError`.
4. Any failure at steps 2–3 (decode error, expired, wrong type, missing user, inactive user)
   is caught by the route and turned into **401 "Invalid or expired refresh token."**
5. On success, `AuthService.refresh_access_token` returns a **brand-new access token only**
   (`RefreshResponse`, `{"access": "...", "token_type": "bearer"}`) — the refresh token
   itself is *not* rotated or reissued; the same refresh token can be used again for the next
   refresh, up until its own 7-day expiry.

Symmetrically, `decode_access_token` rejects a refresh token presented as an access token —
confirmed by `tests/test_auth.py::test_refresh_token_cannot_be_used_as_an_access_token`, which
asserts a refresh token sent as `Authorization: Bearer <refresh token>` to `GET /auth/me`
gets a 401.

---

## 10. Authorisation and roles

**Authentication vs. authorisation.** Authentication (Section 9) answers *"who is this
request from?"* — it always ends with a `User` object or a 401. Authorisation answers
*"is this specific user allowed to do this specific thing?"* — it happens *after*
authentication succeeds, and can still fail with a 403 (wrong role) or a 404 (hidden from
this user entirely, functioning as an ownership-based visibility restriction rather than a
role restriction).

**How 401 errors are produced.** Only from the authentication layer
(`app/dependencies/auth.py`): missing/invalid/expired/wrong-type token, or an inactive user.
Never from a service or a role check.

**How 403 errors are produced.** Two independent mechanisms:
1. `require_roles(*names)` (`app/dependencies/auth.py`) — a dependency *factory*. Each route
   that needs a role gate calls it with the exact allowed role names, e.g.
   `Depends(require_roles("Manager", "Administrator"))`. The returned dependency checks
   `current_user.role.name not in allowed_role_names` and raises 403
   `"You do not have permission to perform this action"` if so. This is the **only** place
   role names are compared against a hard-coded list — it is never duplicated inline in a
   route body (this is stated as a deliberate design rule in the function's own docstring).
2. Domain-level permission exceptions raised by a **service**, translated to 403 by the
   route's `except` block — e.g. `TicketPermissionError` (a Technician trying to view/edit a
   ticket not assigned to them; an Employee trying to view another employee's ticket; a
   non-Manager/Admin trying to set someone else as the requester on `POST /ticket-new`),
   `UserPermissionError` (a non-Admin trying to edit someone else's user profile, or trying
   to set an administrative field on their own), `CommentPermissionError` (editing/deleting a
   comment you didn't author and aren't a Manager/Admin).

**How ownership checks work.** `TicketService._ensure_can_view(ticket, user)`
(`app/services/ticket_service.py`) is the single method every ticket-visibility check funnels
through: Manager/Administrator always pass; a Technician passes only if
`ticket.assigned_technician_id == user.id`; anyone else (Employee) passes only if
`ticket.created_by_user_id == user.id`. This same check backs both `GET /tickets/{id}`
(indirectly, via `get_viewable_ticket` in `app/dependencies/ticket.py`) and every
`/tickets/{id}/...` sub-resource route (comments, attachments, history) — `get_viewable_ticket`
is the one shared dependency every one of those routes uses, so the ownership rule is
implemented exactly once.

**How ticket visibility is restricted (list endpoints).** `TicketService.list_tickets`
forcibly overwrites the caller-supplied `assigned_to`/`created_by` filters based on role,
*before* querying — a Technician's `assigned_to` filter is always replaced with their own id;
an Employee's/other non-Manager's `created_by` filter is always replaced with their own id —
so a client cannot see other users' tickets by manipulating query parameters (confirmed by
`tests/test_ticket_new_endpoints.py::test_all_tickets_employee_cannot_bypass_scope_via_filter`).

**How assignment permission works.** `PATCH /tickets/{id}/assign` is gated by
`require_roles("Manager", "Administrator")` at the route (`_ASSIGN_ROLES` in
`app/api/routes/tickets.py`) — an Employee or Technician cannot call it at all (403 before
the service even runs). Inside `TicketService.assign_technician`, further validation
(`InvalidTechnicianAssignmentError`, → 400) rejects: assigning to a closed ticket, a
nonexistent user id, a user whose role isn't `"Technician"`, or an inactive technician.

**How status-change permission works.** `PATCH /tickets/{id}/status` is gated by
`require_roles("Technician", "Manager", "Administrator")` (`_STATUS_ROLES`) — **an Employee
cannot change status at all.** Inside `TicketService.change_status`, an additional ownership
check applies only to Technicians: if the caller is a Technician *and* not the ticket's
assigned technician, `TicketPermissionError` (403). Managers/Admins may change the status of
any ticket. The requested transition itself is then checked against `_STATUS_TRANSITIONS`
(Section 14); an illegal transition raises `InvalidStatusTransitionError` (409).

**How user-management permission works.** `POST /users` is Administrator-only
(`require_roles("Administrator")`). `GET /users` (list) is Manager-or-Administrator
(`require_roles("Manager", "Administrator")`). `GET /users/{id}` is open to any authenticated
user, but `UserService.get_user_for_viewer` restricts it: Manager/Admin may view anyone;
anyone else may only view their own record (else `UserPermissionError` → 403).
`PATCH /users/{id}` has no route-level role gate beyond "authenticated" — the split happens
entirely inside `UserService.update_user`: if the caller's role is `"Administrator"`, any
field on any user may be changed; otherwise, the caller may only edit **their own** record
(`user_id == current_user.id`), and only the "safe" fields
(`first_name`, `last_name`, `phone_number`, `theme` — the exact set in
`_SELF_EDITABLE_FIELDS`); submitting any other field (even to their own record) is rejected
outright as `UserPermissionError`, not silently ignored. **Notably, a Manager gets no special
privilege here** — despite being allowed to *view* every user and every ticket, a Manager can
only edit their own profile's safe fields, exactly like an Employee or Technician; only an
Administrator can change someone else's role, department, active status, username, or email.
`PATCH /users/me/password` is open to any authenticated user, changing only their own
password (requires the correct current password). `PATCH /users/{id}/password` is
Administrator-only (no current-password check — an intentional admin-reset capability).

### Permissions table (derived directly from route-level `require_roles(...)` calls and the service-level checks described above)

| Action | Employee | Technician | Manager | Administrator |
|---|---|---|---|---|
| View categories/departments/priorities (list/get) | ✅ | ✅ | ✅ | ✅ |
| Create/edit category | ❌ | ❌ | ✅ | ✅ |
| Delete category | ❌ | ❌ | ✅ | ✅ |
| Create/edit department | ❌ | ❌ | ✅ | ✅ |
| Create/edit priority | ❌ | ❌ | ✅ | ✅ |
| `POST /ticket-new` (own ticket) | ✅ | ❌ | ✅ | ✅ |
| `POST /ticket-new` with `requester_user_id` for someone else | ❌ | ❌ | ✅ | ✅ |
| `GET /all-tickets` (own/assigned only) | ✅ | ✅ | ✅ (all) | ✅ (all) |
| `GET /tickets/{id}` (own/assigned only) | ✅ | ✅ | ✅ (any) | ✅ (any) |
| `PATCH /tickets/{id}` (own, only while status = NEW) | ✅ (limited) | ✅ (assigned, any status) | ✅ (any) | ✅ (any) |
| `DELETE /tickets/{id}` | ❌ | ❌ | ✅ | ✅ |
| `PATCH /tickets/{id}/assign` | ❌ | ❌ | ✅ | ✅ |
| `PATCH /tickets/{id}/status` | ❌ | ✅ (assigned only) | ✅ (any) | ✅ (any) |
| Add comment (on a ticket they can view) | ✅ | ✅ | ✅ | ✅ |
| Edit/delete own comment | ✅ | ✅ | ✅ | ✅ |
| Edit/delete anyone's comment | ❌ | ❌ | ✅ | ✅ |
| Upload/download/delete attachment (any, on a viewable ticket) | ✅ | ✅ | ✅ | ✅ |
| View own ticket history | ✅ | ✅ (assigned) | ✅ (any) | ✅ (any) |
| `POST /users` (create user) | ❌ | ❌ | ❌ | ✅ |
| `GET /users` (list all) | ❌ | ❌ | ✅ | ✅ |
| `GET /users/{id}` (self) | ✅ | ✅ | ✅ | ✅ |
| `GET /users/{id}` (someone else) | ❌ | ❌ | ✅ | ✅ |
| `PATCH /users/{id}` (own safe fields) | ✅ | ✅ | ✅ | ✅ |
| `PATCH /users/{id}` (any field, any user) | ❌ | ❌ | ❌ | ✅ |
| `PATCH /users/me/password` (own password) | ✅ | ✅ | ✅ | ✅ |
| `PATCH /users/{id}/password` (reset anyone's) | ❌ | ❌ | ❌ | ✅ |

---

## 11. API routes

See **`docs/BACKEND_API_GUIDE.md`** for the full endpoint-by-endpoint reference (who can call
it, request/response shape, validation, and every possible error response).

---

## 12–20. Ticket lifecycle, statuses, comments, attachments, history, errors, response format, filtering

These topics are covered in full detail in `docs/BACKEND_API_GUIDE.md` (endpoint mechanics)
and `docs/BACKEND_FLOW.md` (the worked end-to-end example). Summary pointers:

- **Ticket lifecycle worked example** → `docs/BACKEND_FLOW.md`, Section "Complete ticket
  lifecycle."
- **Ticket number generation** → `TicketService._generate_ticket_number`
  (`app/services/ticket_service.py`): `f"IT-{year}-{count + 1:06d}"`, where `year` is the
  current UTC year and `count` comes from `TicketRepository.count_for_year(year)`
  (`SELECT COUNT(*) FROM tickets WHERE ticket_number LIKE 'IT-<year>-%'`). Concurrency is
  handled by `TicketService._persist_new_ticket`'s retry loop: if the `INSERT` fails with an
  `IntegrityError` (two concurrent requests computed the same next number and raced for the
  unique `ticket_number` constraint), the session is rolled back and a new number is
  generated, up to 3 attempts, before the error is finally re-raised.
- **Ticket statuses/transitions** → `TicketService._STATUS_TRANSITIONS`
  (`app/services/ticket_service.py`): `NEW → ASSIGNED → IN_PROGRESS ⇄
  WAITING_FOR_EMPLOYEE`, `IN_PROGRESS → RESOLVED → CLOSED`. `CLOSED` is terminal — **no
  reopening is supported** by the code (`_STATUS_TRANSITIONS[TicketStatus.CLOSED] =
  frozenset()`). The `NEW → ASSIGNED` transition happens automatically inside
  `TicketService.assign_technician` (not through `change_status`) the first time a
  technician is assigned to a `NEW` ticket. `resolved_at` is set only on the transition
  *into* `RESOLVED`; `closed_at` only on the transition *into* `CLOSED`.
- **Comments** → author-or-Manager/Admin ownership (`CommentService`); hard `DELETE`, no
  soft-delete; every add/edit/delete writes a `TicketHistory` row.
- **Attachments** → `AttachmentService` + `StorageService`; extension allowlist
  (`.png .jpg .jpeg .pdf .txt .docx .xlsx`), 10 MB default cap, server-generated filenames,
  path-traversal defense, no per-item ownership (anyone who can view the ticket can
  upload/download/delete any attachment on it — a deliberate, documented asymmetry with
  comments).
- **History/auditing** → `HistoryService.record()` is the single code path that ever
  constructs a `TicketHistory` row; actions currently recorded:
  `ticket_created`, `title`, `description`, `location`, `category`, `priority`,
  `assigned_technician`, `status`, `comment_added`, `comment_edited`, `comment_deleted`,
  `attachment_added`, `attachment_deleted`.
- **Error handling** → no global exception handler exists in `app/main.py`; every route
  catches its own service's domain exceptions and maps them to an `HTTPException`. Pydantic
  validation failures become 422 automatically, before any route code runs.
- **Response format** → `DataResponse[T]` (`{data, msg}`) is used by every endpoint added or
  touched in the most recent milestone (Departments, Priorities, Users, `POST /ticket-new`,
  `GET /all-tickets`, `PATCH /tickets/{id}`); every older, untouched endpoint (Categories,
  Comments, Attachments, History, `GET /tickets/{id}`, `assign`, `status`, `Auth`) returns a
  bare object/array/`null` — the project deliberately did **not** retrofit the wrapper onto
  pre-existing endpoints (stated directly in `app/schemas/response.py`'s docstring).
- **Filtering/search/pagination** → `GET /all-tickets` and `GET /users` both support
  filters + `search` + `skip`/`limit`; `GET /all-tickets` additionally supports `sort_by`/
  `sort_dir`. Full parameter tables are in `docs/BACKEND_API_GUIDE.md`.

---

## 21. Tests

**Framework:** `pytest` (v9.1.1). **Test client:** FastAPI's `TestClient`
(`starlette.testclient.TestClient`, built on `httpx`), created inside the shared `client`
fixture in `tests/conftest.py`.

**Test database:** **there is no test database.** Every test runs entirely in-memory — no
SQLite, no real SQL Server connection. This is possible because every `Service` class accepts
its repository as an optional constructor argument (Section 2), so tests inject hand-written
in-memory `Fake*Repository` classes instead of the real, SQLAlchemy-backed ones. `conftest.py`
defines: `FakeUserRepository`, `FakeRoleRepository`, `FakeDepartmentRepository`,
`FakePriorityRepository`, `FakeCategoryRepository`, `FakeTicketRepository`,
`FakeCommentRepository`, `FakeHistoryRepository`, `FakeAttachmentRepository`,
`FakeStorageService`, and `FakeSession` (a no-op `commit()`/`rollback()` stand-in for the
real SQLAlchemy `Session`, since fake repositories already persist in plain Python
dictionaries).

**Fixtures** (all in `tests/conftest.py`): role fixtures (`admin_role`, `employee_role`,
`technician_role`, `manager_role`), user fixtures for every role plus a second employee and
second technician (to test cross-user ownership denial), department/priority/category
fixtures, ticket fixtures (`employee_ticket`, `assigned_ticket`), and the composed `client`
fixture that wires every fake repository into a real FastAPI `TestClient` via
`app.dependency_overrides[get_<x>_service] = lambda: <RealService>(db=FakeSession(),
<x>_repository=<fake>)`.

**Authentication fixtures.** `auth_headers` builds a *real, validly signed* JWT using the
actual `app.core.security.create_access_token` for a given fixture user — so authentication
itself is exercised for real in every test; only the database is faked.

**Dependency overrides.** `app.dependency_overrides` (FastAPI's built-in mechanism) is
populated once per test inside the `client` fixture and cleared at teardown
(`app.dependency_overrides.clear()`), so every `get_db`/`get_<x>_service` a route asks for
resolves to the fake wiring for the duration of that one test.

**Unit vs. integration tests, by file** (all under `tests/`):
- **Pure unit tests, no HTTP, no fakes:** `test_security.py` (hashing/JWT functions called
  directly), `test_roles_dependency.py` (`get_current_active_user`/`require_roles` called
  directly as plain functions), `test_storage_service.py` (the *only* test file that touches
  a real filesystem, via pytest's `tmp_path` fixture — deliberately, since path-traversal
  defense needs to be proven against real `Path` resolution).
- **HTTP integration tests, via `TestClient` + fakes:** `test_auth.py`, `test_categories.py`,
  `test_departments.py`, `test_priorities.py`, `test_locations.py`, `test_users.py`,
  `test_password.py`, `test_tickets.py`, `test_ticket_new_endpoints.py`,
  `test_ticket_history.py`, `test_comments.py`, `test_attachments.py`.

**Permission tests** exist throughout (not a separate file) — e.g.
`test_tickets.py::test_delete_ticket_forbidden_for_non_manage_roles`,
`test_users.py::test_update_user_self_forbidden_from_administrative_field`,
`test_ticket_new_endpoints.py::test_ticket_new_employee_cannot_set_another_requester`.

**Ticket lifecycle tests** — spread across `test_tickets.py` (assign/status/delete),
`test_ticket_new_endpoints.py` (create/list/patch), and `test_ticket_history.py` (every
mutation's audit trail).

**How to run the tests:**

```bash
cd backend
pytest                 # run the whole suite
pytest -q              # quiet summary
pytest tests/test_auth.py       # one file
pytest tests/test_auth.py::test_login_succeeds_with_correct_credentials   # one test
```

**What passing tests prove:** route wiring and dependency injection are correct; every
role/ownership rule behaves as documented; request/response schemas match what the routes
actually send/receive; business-rule edge cases (duplicate usernames, invalid status
transitions, unknown foreign keys, oversized/wrong-type file uploads, path traversal) are
handled the way the code intends. **What they do not prove:** correctness against a real,
Alembic-migrated SQL Server schema — that is verified separately, manually, with
`alembic check` plus a real-database smoke test (not part of the automated `pytest` run).
At last count, the suite has **280 tests**, all passing.

---

## 22. Security review

### Implemented protections (confirmed in the code)

- **Password hashing** — Argon2 via `pwdlib.PasswordHash.recommended()`
  (`app/core/security.py`); plaintext is never stored or logged.
- **JWT validation** — signature verification, `sub`/`type` claim checks, expiry checks, all
  centralized in `app/core/security.py`; access and refresh tokens are cryptographically
  distinct via the `"type"` claim, so one can never be substituted for the other (Section 9).
- **Refresh-token handling** — a refresh token is required to mint a new access token; a
  deactivated or deleted user's refresh token is rejected even if not yet expired.
- **Role-based permissions** — enforced in exactly one place, `require_roles()`, never
  duplicated ad hoc.
- **Ownership checks** — `TicketService._ensure_can_view`, `CommentService`'s author check,
  `UserService`'s self-vs-admin field split — all centralized in their respective services.
- **Input validation** — every request body is a Pydantic model; several add
  `@field_validator`s to reject blank/whitespace-only strings.
- **ORM protection from SQL injection** — every query in `app/repositories/` is built with
  SQLAlchemy's `select()`/query builder and bound parameters; the *only* raw SQL in the
  entire codebase is inside Alembic migration scripts (`op.execute(...)`), used for one-time
  data backfills with no user-controlled input, never in a request-serving code path.
- **File validation** — extension allowlist, size cap, server-generated (UUID) filenames,
  and explicit path-traversal defense (`StorageService._resolve`, which rejects any resolved
  path outside the storage root).
- **Secret management (dev-appropriate)** — `SECRET_KEY` and DB credentials come from a
  git-ignored `.env` file; only a placeholder `.env.example` is committed.
- **Inactive-user checks** — enforced both at login and on every subsequent authenticated
  request.

### Limitations / required before a real production deployment

| Area | Status found in the code | What's needed |
|---|---|---|
| HTTPS | Not configured anywhere in the app (this is normally a reverse-proxy/deployment concern, not application code) | Terminate TLS in front of the app; nothing in `app/main.py` enforces or assumes HTTPS today |
| Token revocation | None — no server-side token store, no logout endpoint that invalidates a specific token; a leaked refresh token stays valid for up to 7 days | A revocation list / short-lived refresh tokens with rotation, or a server-side session store |
| Rate limiting | None found on `/auth/login` or any other route | Add rate limiting (e.g. per-IP/per-account) to slow brute-force password guessing |
| Antivirus/content scanning | Only file **extension** and **size** are checked (`AttachmentService.upload_attachment`) — file *content* is never scanned | Integrate a malware scanner before accepting uploads in production |
| Cloud/redundant file storage | Files are written to local disk (`storage/attachments/`) — a single point of failure | Move to object storage (e.g. S3/Azure Blob) with redundancy for real deployments |
| Logging/monitoring | No structured application logging or metrics/alerting code found beyond Alembic's own log config | Add request/error logging and monitoring before production |
| CORS | **`app/main.py` registers no `CORSMiddleware` at all** | Required even for local development against a browser-based React frontend on a different origin — not just a production concern |
| Production secret storage | `.env` file (fine for a university project, git-ignored) | A managed secret store (Key Vault / Secrets Manager / env vars injected by the deployment platform) |
| Database backups | Not part of the application code — **Not confirmed from the code**; this is an infrastructure/ops concern outside `backend/` | Define and test a backup/restore strategy |
| JWT signing key strength | The dev `SECRET_KEY` used in tests is short enough to trigger PyJWT's own `InsecureKeyLengthWarning` (below the 32-byte minimum recommended for HS256) | Use a properly long, random `SECRET_KEY` in any real deployment |

**Clearly separating the two categories:** everything in "Implemented protections" is
**good enough for this university project** — it demonstrates real, correctly-applied
security fundamentals (hashing, JWT, RBAC, ownership checks, SQL-injection-safe querying,
file-upload validation). Everything in the limitations table is **required before a real
production deployment**, none of it is a flaw in how the existing code was written — these
are simply concerns a student project is not expected to have solved yet, and the code
never claims otherwise.

### Discrepancy found: `docs/database-design.md` vs. the actual code

`docs/database-design.md` is the project's original design document. It predates the most
recent backend milestone and is now **out of date** in several concrete ways confirmed
against the actual models/migrations:
- It describes `users.department` as a free-text string column and lists no `departments`
  table — the code now has a real `Department` model/table and `User.department_id` FK.
- It describes `tickets.priority` as a `String(20)` enum column (`LOW`/`MEDIUM`/`HIGH`/
  `CRITICAL`) — the code now has a real `Priority` model/table and `Ticket.priority_id` FK.
- It does not mention `username`, `phone_number`, `theme` on `User`, or `location` on
  `Ticket` — all four exist in the current model.
- It does not mention refresh tokens or the `/ticket-new` / `/all-tickets` / `PATCH
  /tickets/{id}` endpoints.

This is not a bug in the running system — the *code* is internally consistent and the live
database matches the code (`alembic check` reports no drift) — but the design document itself
has not been updated to match, and a professor comparing the two side by side would notice
the mismatch. This documentation set (the `docs/BACKEND_*.md` files) reflects the actual,
current code.

### Consistency/quality review findings (most recent pass)

A dedicated review pass across the whole codebase — code duplication, naming, relationships,
validation, status codes, error messages, database indexes/cascades — found two real bugs
(both fixed) and a set of judgment-call recommendations left as-is (not silently changed):

**Bugs found and fixed:**
1. `TicketRepository._EAGER_OPTIONS` was never updated when `Ticket.location` was added,
   unlike `category`/`priority`/`created_by`/`assigned_technician` — every ticket response
   was silently issuing an extra lazy-load query per ticket. Fixed by adding
   `selectinload(Ticket.location)`.
2. `TicketService.delete_ticket` cascaded the DB rows for a ticket's comments/attachments/
   history but never deleted the physical attachment files from disk, unlike
   `AttachmentService.delete_attachment` (which correctly cleans up) — deleting any ticket
   with attachments leaked files on disk forever. Fixed by capturing each attachment's
   `file_path` before the cascade delete, committing, then deleting each physical file
   afterward (same ordering rationale as the single-attachment delete path). Covered by a new
   regression test, `test_delete_ticket_removes_its_attachments_physical_files`.

**Recommendations left as-is (not code changes):**
- Naming: `Category` uses `name`; `Department`/`Priority`/`Location` use `title` — a
  historical inconsistency, not worth a breaking rename now.
- `DepartmentService`/`PriorityService`/`LocationService` are near-identical duplicated CRUD
  services by design (matching existing project precedent of favoring explicit code over a
  shared abstraction for three small, similar entities).
- `Category.is_active` is dead weight (see above) while `Department`/`Priority` have no
  equivalent flag at all, despite the same lifecycle need `Location.is_active` now serves.
- Comment routes explicitly declare `require_roles(*_VIEW_ROLES)`; attachment routes rely on
  bare `get_current_active_user` — functionally identical today (only four roles exist) but
  stylistically inconsistent.
- `UserCreate.email`/`UserUpdate.email` are plain `str`, not validated as real email
  addresses — using Pydantic's `EmailStr` would require adding the `email-validator`
  dependency, which isn't currently installed; not added unilaterally.
- `username` has no charset restriction; password policy is length-only (`min_length=8`, no
  complexity requirement) — acceptable for a university project.
- **No index exists on any foreign-key column**, confirmed against the live database (see
  the Indexes note in Section 5) — the single highest-value database improvement available.
- Cascades (`Ticket.comments/attachments/history`) are ORM-level only, not
  `ON DELETE CASCADE` at the database level — correct for every code path the app actually
  uses, but not defense-in-depth against a raw SQL delete.

---

## 23. React frontend integration

Nothing in `backend/` is React-specific — the backend is a plain JSON API, so any frontend
(React, another framework, or `curl`) integrates the same way. This section describes how a
React app would use it, based purely on what the endpoints documented above actually accept
and return; **not** a claim that a frontend currently exists in this repository.

**Login.** `POST /auth/login` with `{"username": ..., "password": ...}`. On success, store
`access` and `refresh` from the response — typically in memory (e.g. a React context/store)
rather than `localStorage`, to reduce XSS exposure, though the backend itself has no opinion
on where the frontend keeps them.

**Authorization header.** Every subsequent request attaches
`Authorization: Bearer <access token>`. In practice this means a shared `fetch`/`axios`
wrapper that reads the current access token out of app state and adds the header
automatically, rather than every component doing it manually.

**Refreshing tokens.** When a request comes back `401` because the access token expired, call
`POST /auth/refresh` with the stored refresh token, get a new `access` token back, retry the
original request once. If the refresh call *itself* returns 401 (the refresh token expired
or was rejected), the frontend should treat that as a full logout — there is no way to
recover a session at that point, since the backend never issues a new refresh token from
`/auth/refresh` (only a new access token — see §9).

**Loading the current user.** `GET /auth/me` after login (or on app load, if a token is
already stored) — its `CurrentUserResponse` includes `role`, which is what the frontend would
use to decide what to show (see "role-based screens" below).

**Fetching lists.** `GET /all-tickets`, `GET /categories`, `GET /departments`,
`GET /priorities`, `GET /locations`, `GET /users` — remember that
`/all-tickets`/`/departments`/`/priorities`/`/locations`/`/users` responses are wrapped
(`response.data.data`), while `/categories` is bare (`response.data`) — a frontend
data-fetching layer needs to know this per-endpoint, since it is not consistent (§19/22).

**Creating tickets.** `POST /ticket-new` with `title`, `description`, `location_id`,
`category_id`, `priority_id` — the frontend needs `category_id`/`priority_id`/`location_id`
values, which means fetching `GET /categories`, `GET /priorities`, and `GET /locations` first
(e.g. to populate dropdowns) - for locations, filtering the dropdown to only
`is_active: true` entries client-side, since the backend returns all of them but rejects an
inactive one being newly selected.

**Uploading files.** `POST /tickets/{id}/attachments` as `multipart/form-data` with a `file`
field — in a browser, this is a `FormData` object passed to `fetch`/`axios`, not JSON; the
`Content-Type: multipart/form-data` header (with the correct boundary) must be set by the
HTTP client, not hand-written.

**Displaying errors.** Every error response is `{"detail": "..."}` (FastAPI's default
`HTTPException` shape) except `422` validation errors, which return `{"detail": [...]}` — an
array of structured field-level errors. A frontend error handler needs to branch on status
code: 401 → redirect to login / attempt refresh; 403 → "you don't have permission"; 404 →
"not found"; 409 → show the conflict message (e.g. duplicate username); 422 → map each
array entry back to its form field.

**Role-based screens.** Since the backend enforces every permission server-side regardless of
what the frontend shows, the frontend's role-based UI (e.g. hiding the "Assign technician"
button from an Employee) is purely a UX convenience — it must not be relied on as the actual
security boundary, because the backend will 403 the request anyway if attempted directly.

**Logging out.** There is no `POST /auth/logout` endpoint and no server-side token
invalidation (§22) — "logging out" in a frontend built against this backend, as it stands
today, means discarding the stored tokens client-side; the tokens themselves remain valid
until they naturally expire.

**Example flow (login → create a ticket):**

```
1. POST /auth/login {username, password} → {access, refresh}
2. GET /auth/me  (Authorization: Bearer <access>) → current user + role
3. GET /categories, GET /priorities  → populate the "new ticket" form's dropdowns
4. POST /ticket-new {title, description, category_id, priority_id}  → new ticket
5. If step 4 returns 401 → POST /auth/refresh {refresh} → retry step 4 with the new access token
```

**One concrete blocker for a browser-based React app today:** `app/main.py` does not
register `CORSMiddleware`. A React dev server on a different origin (e.g.
`http://localhost:3000` calling `http://localhost:8000`) would have its requests blocked by
the browser before the backend even sees them, until CORS is configured — this is required
for local development against a browser, not only for production.

---

## 24. Swagger

**Why Swagger is available.** FastAPI generates an OpenAPI schema automatically from every
route's declared path, HTTP method, parameters, request/response Pydantic models, and
security requirements — no separate documentation-writing step is needed; the schema is a
byproduct of the same type annotations that drive request validation.

**How FastAPI generates it.** As soon as `app = FastAPI(...)` is created and routes are
included (`app/main.py`), FastAPI can produce `GET /openapi.json` on demand, and serves
interactive Swagger UI at `GET /docs` (and ReDoc at `GET /redoc`) built on top of that same
schema — none of this required any extra code in this project; it is FastAPI's default
behavior whenever `docs_url`/`openapi_url` are not overridden (they aren't, here).

**How "Authorize" works.** Because `app/dependencies/auth.py` declares its security
requirement using FastAPI/Starlette's `HTTPBearer(auto_error=False)` scheme
(`bearer_scheme`), FastAPI records a Bearer-token security scheme in the OpenAPI spec. This
is what makes the padlock icon and the **Authorize** button appear in Swagger UI — clicking
it and pasting a raw access token (obtained from trying `POST /auth/login` first) attaches
`Authorization: Bearer <token>` to every subsequent "Try it out" request made from that
Swagger session.

**How to test protected routes in Swagger.** 1) Expand `POST /auth/login`, "Try it out",
submit valid credentials, copy the `access` value from the response. 2) Click **Authorize**
at the top of the page, paste the token, confirm. 3) Any route requiring authentication can
now be tried directly from the UI — Swagger attaches the header automatically.

**How multipart file upload appears.** Because `POST /tickets/{id}/attachments` declares its
parameter as `file: UploadFile = File(...)` (`app/api/routes/attachments.py`), FastAPI marks
that parameter as `multipart/form-data` in the OpenAPI schema, and Swagger UI renders it as a
native file-picker widget — a real file can be selected from disk and uploaded directly from
the browser, no separate tool needed.

**Why Swagger is useful for demonstrating the backend before a React frontend exists.** It
gives a complete, interactive, zero-code way to exercise every endpoint — login, refresh,
CRUD on every resource, ticket lifecycle transitions, file upload/download — directly against
the real backend and real database, which is exactly what makes it suitable for a live
professor demonstration without needing to build or run a frontend first.

---

## 25. End-to-end flow summary

1. Client sends an HTTP request (JSON or multipart), with `Authorization: Bearer <token>` if
   the endpoint requires authentication.
2. FastAPI matches the request to a route function by method + path
   (`app/api/router.py` → the specific file in `app/api/routes/`).
3. FastAPI resolves that route's `Depends(...)` dependencies, in order — this always starts
   with `get_db()` opening one SQLAlchemy `Session` for the request.
4. If the route requires authentication, `get_current_user`/`get_current_active_user`
   (`app/dependencies/auth.py`) decodes the JWT from the Authorization header and loads the
   corresponding `User` row fresh from the database — failing here returns **401**.
5. If the route requires a specific role or ticket ownership,
   `require_roles(...)`/`get_viewable_ticket` checks it — failing here returns **403** (or
   **404**, for a ticket that exists but this user cannot see).
6. If the route accepts a body, Pydantic validates it against the route's declared schema —
   failing here returns **422**, before any business logic runs.
7. The route function's own body runs — a few lines that call exactly one method on a
   Service (`app/services/*.py`).
8. The Service applies business rules (uniqueness, ownership, status-workflow legality) and
   calls its Repository (`app/repositories/*.py`) to read/write data via SQLAlchemy.
9. If the operation is a ticket-related mutation, the Service also calls
   `HistoryService.record(...)` to write an audit row.
10. The Service commits the transaction (`db.commit()`) — or rolls it back and raises/retries
    if a database constraint was violated.
11. If the Service raised a domain exception (e.g. `TicketNotFoundError`,
    `UsernameConflictError`), the route's own `except` block catches it and raises the
    matching `HTTPException` (**400/404/409**, as appropriate).
12. Otherwise, the ORM object(s) the Service returned are serialized by the route's
    `response_model` — a Pydantic schema that determines exactly which fields appear in the
    JSON (and guarantees fields like `password_hash` never can, since they're simply not
    declared on any response schema).
13. FastAPI sends the resulting JSON (or, for file downloads, raw bytes with a
    `Content-Disposition` header) back to the client as the HTTP response.
14. `get_db`'s `finally: db.close()` runs, releasing the database session back to the pool,
    regardless of whether the request succeeded or failed.
