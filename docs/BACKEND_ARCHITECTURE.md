# ITOnIT Backend — Architecture Reference

This document describes the **final, as-built** ITOnIT backend: a multi-tenant
FastAPI application backing tickets, inventory, analytics, company
administration, and platform administration. It replaces an earlier version of
this file that predated the entire multi-tenant migration (Company entity,
`company_id` scoping, roles beyond Employee/Technician, inventory, analytics,
the platform console) — see `docs/TECH_DEBT.md` for that history. Every claim
below was verified directly against the code in this repository, not carried
over from the earlier draft.

## 1. Backend overview

ITOnIT's backend is a layered FastAPI application:

```
Route (app/api/routes/*.py)
  → Dependency injection (app/dependencies/*.py) — auth, roles, company scope, DB session
  → Pydantic schema validation (app/schemas/*.py)
  → Service (app/services/*.py) — business rules, transaction boundary, domain exceptions
  → Repository (app/repositories/*.py) — SQLAlchemy queries, company-scoped
  → SQLAlchemy model (app/models/*.py) — one of 15 tables
  → SQL Server
```

A route function is deliberately thin: resolve dependencies, call exactly one
service method, translate that method's domain exceptions into HTTP status
codes. All business logic — ownership rules, validation that depends on more
than one field, state transitions — lives in the service layer, never in a
route or a repository. Repositories only build/run queries and `flush()`;
`commit()`/`rollback()` belong to the service that orchestrates one or more
repository calls, so a multi-step write (e.g. create a ticket *and* write a
history row) is one atomic transaction.

**Multi-tenancy is the organizing principle of this whole layer stack.** Every
tenant-owned table carries a `company_id`, every tenant-scoped
repository/service is constructed with the authenticated caller's own
`company_id` (never a client-supplied value — see §5), and the one
platform-level System Administrator account is served by an entirely separate
route group that never goes through that scoping mechanism at all.

## 2. Project structure — file by file

```
backend/
├── app/
│   ├── main.py            FastAPI app creation, CORS, router mounting
│   ├── api/
│   │   ├── router.py       Combines every route module into api_router
│   │   └── routes/         One file per resource (18 files — see §11)
│   ├── core/
│   │   ├── config.py       Settings (pydantic-settings), loaded from backend/.env
│   │   ├── security.py     Argon2 hashing, JWT create/decode (access + refresh)
│   │   └── time.py         utc_now_naive(), local day/month boundary helpers for analytics
│   ├── db/
│   │   └── database.py     SQLAlchemy engine, SessionLocal, declarative Base
│   ├── models/             15 SQLAlchemy ORM models + mixins.py (timestamps) + enums.py
│   ├── schemas/            Pydantic request/response models, one file per resource
│   ├── repositories/       base.py (BaseRepository, CompanyScopedRepository) + one per resource
│   ├── services/           Business logic, one file per resource/concern
│   ├── dependencies/       FastAPI DI wiring: auth.py, ticket.py, ticket_inventory.py, ...
│   └── scripts/
│       └── seed_initial_data.py   Bootstraps roles, the Default Company, and optional admin accounts
├── scripts/
│   └── create_demo_users.py       Dev-only: four demo accounts on the Default Company
├── alembic/                Migration environment and every version file
├── storage/
│   ├── attachments/         Uploaded ticket files (not committed)
│   └── logos/                Uploaded company logos (not committed)
└── tests/                   pytest suite — conftest.py + one file per feature/route group
```

### Key files

- **`app/main.py`** — creates the `FastAPI` app, attaches `CORSMiddleware`
  (allowed origins from `settings.CORS_ORIGINS`), mounts `api_router`.
- **`app/api/router.py`** — one `APIRouter` combining every resource's router;
  `tickets.py` contributes *two* routers (`router`, prefixed `/tickets`, and
  `flat_router`, unprefixed, for `/ticket-new` and `/all-tickets`).
- **`app/core/config.py`** — a `pydantic-settings` `Settings` class, cached via
  `lru_cache`; see §4 for the full variable list.
- **`app/core/security.py`** — `hash_password`/`verify_password` (Argon2, via
  `pwdlib.PasswordHash.recommended()`), and `create_access_token`/
  `create_refresh_token`/`decode_access_token`/`decode_refresh_token` (PyJWT,
  each token carrying a `"type"` claim so an access token can never be used
  where a refresh token is required, and vice versa).
- **`app/repositories/base.py`** — `BaseRepository` (generic CRUD) and
  `CompanyScopedRepository` (adds the `company_id` filter — see §5).
- **`app/dependencies/auth.py`** — `get_current_user`, `get_current_active_user`
  (also checks the user's company is active), `get_current_company_id` (the
  **one** place any tenant-scoped repository/service gets its `company_id`
  from), and `require_roles(...)`.

## 3. Application startup flow

1. `uvicorn app.main:app` imports `app.main`, which imports `app.core.config`
   (`Settings()` parses `backend/.env` once, cached), then builds the
   `FastAPI` instance and attaches CORS middleware using
   `settings.CORS_ORIGINS`.
2. `app.api.router.api_router` is imported, which imports every route module —
   each route module's top-level code builds its `APIRouter` and its
   module-level role-name tuples (e.g. `_MANAGE_ROLES = ("Company
   Administrator",)`), but registers no database connection at import time.
3. `app.include_router(api_router)` mounts every route.
4. No database migration or seeding runs automatically on startup — `alembic
   upgrade head` and `seed_initial_data`/`create_demo_users` are explicit,
   separate steps (see the root README).
5. Each request opens its own SQLAlchemy `Session` via `Depends(get_db)`
   (`app/dependencies/database.py`), closed at the end of the request.

## 4. Configuration and environment variables

`app/core/config.py`'s `Settings` (pydantic-settings, `extra="ignore"` — an
unknown environment variable, or an unknown JSON field in a request body from
a stale client, is silently ignored rather than rejected):

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `ITOnIT API` | Swagger/OpenAPI title |
| `APP_VERSION` | `1.0.0` | Swagger/OpenAPI version |
| `DATABASE_SERVER` / `DATABASE_NAME` | — (required) | SQL Server connection |
| `DATABASE_DRIVER` | `ODBC Driver 17 for SQL Server` | pyodbc driver name |
| `DATABASE_USERNAME` / `DATABASE_PASSWORD` | unset | Unset → Windows Trusted Connection |
| `SECRET_KEY` | — (required) | JWT signing key |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | Refresh token lifetime — must outlive the access token |
| `INITIAL_ADMIN_EMAIL`/`_PASSWORD`/`_FIRST_NAME`/`_LAST_NAME` | unset | Optional Default-Company admin, seeded by `seed_initial_data` |
| `PLATFORM_ADMIN_EMAIL`/`_PASSWORD`/`_FIRST_NAME`/`_LAST_NAME` | unset | Optional platform-level System Administrator, seeded by the same script |
| `ATTACHMENT_STORAGE_PATH` | `storage/attachments` | Ticket file storage root |
| `MAX_ATTACHMENT_SIZE_BYTES` | `10485760` (10 MB) | Upload cap |
| `LOGO_STORAGE_PATH` | `storage/logos` | Company logo storage root |
| `MAX_LOGO_SIZE_BYTES` | `2097152` (2 MB) | Logo upload cap |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed browser/Electron origins |

Database URL assembly (`app/db/database.py`): if both `DATABASE_USERNAME` and
`DATABASE_PASSWORD` are set, a SQL-authenticated `mssql+pyodbc://` URL is
built; otherwise the connection uses Windows Trusted Connection.

## 5. Database architecture — multi-tenancy

**Company is the tenant boundary.** Every table other than `companies` and
`roles` is either directly `company_id`-owned (`users`, `departments`,
`priorities`, `categories`, `locations`, `tickets`, `inventory_categories`,
`inventory_items`) or carries `company_id` **denormalized from its parent**
(`comments`, `attachments`, `ticket_history`, `ticket_inventory_usage`,
`inventory_transactions` — each reachable only via a company-owned parent, but
carrying the column anyway so isolation is mechanical, not "remember to join
through the parent").

**`CompanyScopedRepository`** (`app/repositories/base.py`) is what makes that
isolation structural rather than a convention every query has to remember:

- Constructed with `(db, model, company_id)` — every subclass is instantiated
  with the *authenticated caller's own* `company_id`, resolved by
  `get_current_company_id` and never accepted from client input anywhere.
- Overrides `get_by_id`/`get_all` to always filter by `self.company_id`, so a
  cross-company id resolves to "not found," identical to one that never
  existed — never a distinct "wrong company" error, and never a silent leak.
- Every bespoke query method a subclass adds (`get_by_title`,
  `get_with_filters`, `list_for_ticket`, …) must add its own
  `company_id == self.company_id` predicate — the base class has no way to
  see into those statements, so this is a real, load-bearing convention, not
  automatic for free.

**`UserRepository` is the one exception** — it is *not* built on
`CompanyScopedRepository`, because authentication needs to resolve "who is
this JWT for" before any company is known at all. It supports an unscoped
construction (`UserRepository(db)`, `company_id=None`) used only by auth code
and by `PlatformService`'s one legitimate cross-tenant query
(`count_all_tenant_users`); every tenant-scoped service still constructs it
with an explicit `company_id`.

**The System Administrator is the one row with `company_id IS NULL`.** It is
never returned by any company-scoped query, never reachable through
`get_current_company_id` (which raises a 403 for a company-less caller), and
is served exclusively by the separate `/platform/...` route group (§14).

**Company suspension:** deactivating a company (`is_active = False`,
System-Administrator-only) blocks new logins/resolves at
`AuthService.resolve_company`/`authenticate`, and blocks every
already-authenticated request — including one holding a still-valid,
unexpired access token — via `get_current_active_user`'s
`current_user.company.is_active` check on every request. No tenant data is
touched by suspension; reactivating restores access with no other side
effect.

**Row-level security is enforced at the application layer (repository +
service), not by any SQL Server engine-level feature** (no Row-Level Security
policies, no per-tenant schema/database) — worth stating explicitly, since
"multi-tenant" can otherwise be assumed to mean either.

## 6. Alembic and migrations

- `backend/alembic/` holds the migration environment and every version file,
  each with an explicit `down_revision` chain — `alembic heads` must always
  show exactly one head.
- Migrations are applied with `alembic upgrade head`; `alembic current` shows
  the database's revision; `alembic check` verifies the live models match the
  database with no drift.
- The most recent migration is `aa1908b341bb` (drops `companies.theme` and
  `users.theme` — see `docs/database-design.md` §18 and `docs/TECH_DEBT.md`).
- SQL Server specifics this schema's migrations have had to handle directly:
  autogenerated default-constraint names must be discovered dynamically
  (`sys.default_constraints`) before a column carrying one can be dropped;
  `DATETIME2(3)` is used everywhere instead of `DATETIME` (see the UTC
  timestamp note in `docs/TECH_DEBT.md`); enum-like columns are plain
  `VARCHAR` with an explicit `CHECK` constraint, not SQL Server's own enum
  type (which doesn't exist).
- Historical migrations are never edited after the fact — a schema
  correction is always a new migration with its own `down_revision`.

## 7. Database models and relationships

Full column-by-column detail for all 15 tables lives in
[`docs/database-design.md`](database-design.md) — this section only
summarizes the shape. Companies, Roles, Users, Departments, Priorities,
Categories, Locations, Tickets, Comments, Attachments, TicketHistory,
InventoryCategories, InventoryItems, InventoryTransactions, and
TicketInventoryUsage.

Two facts worth stating here directly, since they're the ones a stale
document is most likely to get wrong:

- **`Attachment` has a `ticket_id` FK and no `comment_id` column or
  relationship at all.** An attachment belongs to exactly one entity, its
  ticket — never optionally to a comment.
- **`Ticket.location_id`** is a nullable FK to `locations.id` — a ticket's
  location is chosen from a company-managed list, never free text.

`CreatedAtMixin`/`TimestampMixin` (`app/models/mixins.py`) generate every
`created_at`/`updated_at` in application code as naive UTC
(`app.core.time.utc_now_naive`) — the sole write mechanism this codebase
relies on; a `server_default=SYSUTCDATETIME()` exists purely as a
defense-in-depth fallback for a write path that bypasses the ORM, which
normal application traffic never does.

## 8. Pydantic schemas

`app/schemas/*.py`, one file per resource, following a consistent shape per
resource: a `*Create` (POST body), a `*Update`/`*Patch` (PATCH body, partial —
uses `model_fields_set` so an omitted field is left alone while an explicit
`null` clears a nullable one), and a `*Response` (`model_config =
ConfigDict(from_attributes=True)`, built directly from the ORM object).

- `DataResponse[T]` (`app/schemas/response.py`) is a `{data, msg}` envelope
  used by every endpoint built from Milestone 5 onward (Users, Departments,
  Priorities, Locations, Categories's own list/get, `/ticket-new`,
  `/all-tickets`, every Inventory/Analytics/Platform endpoint). A handful of
  earlier endpoints (`/auth/*`, ticket detail/patch/assign/status, comments,
  attachments) predate this convention and return their bare shape instead —
  deliberately not retrofitted.
- `UTCDatetime` (`app/schemas/types.py`) is a Pydantic `Annotated` type that
  attaches an explicit UTC suffix to every serialized system timestamp, so a
  JSON response's `created_at` etc. always carries `Z`/`+00:00` and the
  frontend's `new Date(...)` parses it correctly.
- **Unknown fields are silently ignored** (`extra="ignore"` at the model
  config level used throughout): a stale client sending a removed field like
  `theme` gets a normal `200`/`201` response with no `theme` in it, not a
  `422`.

## 9. Authentication flow

Two independent login flows share the same JWT mechanism.

### Tenant login

1. `POST /auth/resolve-company {company_code}` — public. Looks up the company
   by its code and returns its name/logo for the login screen to show before
   asking for credentials. Deliberately **does** reveal whether a code exists
   and whether it's suspended (`404`/`403`) — company codes are meant to be
   shared among a company's own employees, not secrets.
2. `POST /auth/login {company_code, username, password}` — public.
   `AuthService.authenticate` resolves the company, then looks the user up
   *within that company* by username or email, verifies the Argon2 hash, and
   checks `is_active`. Every failure mode (unknown company, unknown user,
   wrong password, inactive account) collapses into the **same** `401
   InvalidCredentialsError` — deliberately non-disclosing, so a caller can't
   use the response to probe which company codes or usernames are valid. A
   suspended company gets its own distinct `403`, since that's considered
   acceptable, honest disclosure (same as step 1).
3. Success issues a JWT **access token** (short-lived,
   `ACCESS_TOKEN_EXPIRE_MINUTES`) and **refresh token** (longer-lived,
   `REFRESH_TOKEN_EXPIRE_MINUTES`), each carrying a `"type"` claim
   (`"access"`/`"refresh"`) so one can never be substituted for the other.
4. `GET /auth/me` resolves the current user from the access token on every
   subsequent request via `get_current_user` → `get_current_active_user`.
5. `POST /auth/refresh {refresh}` exchanges a valid, unexpired refresh token
   for a new access token — the frontend's Axios response interceptor calls
   this automatically on any `401`, then retries the original request, which
   is what makes a page reload not require a full re-login (see §19).

**Passwords** are hashed with **Argon2** (`pwdlib.PasswordHash.recommended()`)
— never stored or logged in plaintext anywhere.

**Logout is client-side only**: it clears the stored access/refresh tokens
and nothing else. There is **no server-side token revocation/blocklist** in
V1 — a still-valid, unexpired token issued before logout would still be
accepted by the API if replayed. This is documented current V1 behavior, not
a bug — see `docs/TECH_DEBT.md`.

### Platform login

`POST /platform/login {username, password}` is a separate, parallel flow with
**no `company_code`** — it resolves only the single row with `company_id IS
NULL` (`UserRepository.get_platform_administrator`), never falls back to a
tenant lookup, and shares the identical non-disclosure contract (unknown
identifier, wrong password, inactive account, or an identifier belonging to a
real tenant user all collapse into the same `401`). Token issuance
(`issue_tokens`) is shared code with tenant login — the tokens themselves are
not distinguishable by type, only by which account id they carry; every
`/platform/...` route re-checks the role on every request via
`require_roles("System Administrator")`.

## 10. Authorization and roles

Exactly **four roles** exist in the final schema, seeded once, platform-wide:
`Employee`, `Technician`, `Company Administrator`, `System Administrator`.
There is no "Manager" role and no bare "Administrator" role — those were
early design-draft names, consolidated into `Company Administrator` before
the multi-tenant migration was even complete (see `docs/TECH_DEBT.md`). Any
number of Company Administrators may exist per company, all with identical
permissions — it is not a singular role.

`require_roles(*names)` (`app/dependencies/auth.py`) builds a FastAPI
dependency that checks `current_user.role.name` against an allow-list,
raising `403` otherwise. Ticket/comment/attachment/inventory-usage routes
additionally enforce **ownership**, not just role, via
`get_viewable_ticket`/service-level checks (§12) — a Technician who is not
the assigned technician on a given ticket is refused even though the role
check alone would pass.

### Responsibilities, by role (verified against the actual route/service gates)

**Employee**
- Create tickets (`POST /ticket-new`, as themselves).
- View/comment/attach only on tickets they created
  (`TicketService.resolve_ownership_scope`).
- Ticket analytics scoped to tickets they created; **no** inventory access or
  inventory analytics anywhere.

**Technician**
- Work tickets assigned to them: change status, comment, attach, view
  history.
- Read inventory items/categories; **reserve, consume, and release**
  inventory against a ticket assigned to them (never **undo a consumption** —
  that's Company-Administrator-only).
- Ticket and inventory analytics scoped to their own assigned
  tickets/reservations.

**Company Administrator**
- Company-wide ticket access: assign a technician, delete a ticket, patch any
  ticket regardless of status.
- Manage users (create/edit/deactivate — never hard-delete), reference data
  (departments/priorities/categories/locations), and inventory
  (create/edit items and categories, view the full company-wide inventory
  transaction feed).
- Company settings (name, company code, contact email, logo).
- Full, company-wide ticket and inventory analytics.
- The only role that can undo a consumed inventory usage.

**System Administrator**
- `company_id IS NULL` — a single account, served exclusively by
  `/platform/...` routes and `POST /platform/login`.
- Platform overview, company list/search, company detail (with aggregate
  counts), activate/deactivate a company, provision a new company on a
  customer's behalf.
- **No tenant data access through any normal tenant endpoint** — there is no
  code path where `get_current_company_id` succeeds for this account, so
  `/tickets`, `/users`, `/inventory-*`, etc. are all unreachable for it (a
  `403`, same as any other company-less request).

### Ownership rule reference

`TicketService.resolve_ownership_scope` (reused verbatim by
`AnalyticsService`, never re-derived) is the **one** canonical rule for who
can see which tickets:

| Caller | Scope |
|---|---|
| Company Administrator | every ticket in the company |
| Technician | only tickets where `assigned_technician_id == self` |
| Employee | only tickets where `created_by_user_id == self` |

## 11. API routes

18 route modules, mounted by `app/api/router.py`. Full endpoint-by-endpoint
detail (method, path, roles, request/response shape, error mapping) is in
[`docs/BACKEND_API_GUIDE.md`](BACKEND_API_GUIDE.md); this is the map of route
groups:

| Module | Prefix | Covers |
|---|---|---|
| `health.py` | — | `GET /health`, `GET /` |
| `auth.py` | `/auth` | Tenant login/refresh/me/resolve-company |
| `companies.py` | `/companies` | Registration, own-company settings + logo |
| `platform.py` | `/platform` | Platform login, overview, company list/detail/activate/deactivate/create |
| `users.py` | `/users` | User CRUD, password changes |
| `departments.py` | `/departments` | Department CRUD (no delete) |
| `priorities.py` | `/priorities` | Priority CRUD (no delete) |
| `locations.py` | `/locations` | Location CRUD (deactivate, no delete) |
| `categories.py` | `/categories` | Ticket-category CRUD (real delete, blocked if in use) |
| `inventory_categories.py` | `/inventory-categories` | Inventory-category CRUD (no delete) |
| `inventory_items.py` | `/inventory-items` | Inventory-item CRUD + per-item transaction history |
| `inventory_transactions.py` | `/inventory-transactions` | Company-wide transaction feed (Company Administrator only) |
| `tickets.py` | `/tickets`, plus flat `/ticket-new`/`/all-tickets` | Ticket CRUD, assign, status, comments, history, ticket-scoped inventory |
| `attachments.py` | `/tickets/{ticket_id}/attachments` | Upload/list/download/delete |
| `analytics.py` | `/analytics` | Ticket and inventory analytics |

## 12. Ticket lifecycle, comments, attachments, history

**Status workflow** (`TicketService._STATUS_TRANSITIONS`, enforced strictly —
any other transition is a `409`):
`NEW → ASSIGNED → IN_PROGRESS ⇄ WAITING_FOR_EMPLOYEE → RESOLVED → CLOSED`.
`ASSIGNED` is entered automatically when a technician is first assigned to a
`NEW` ticket. `resolved_at`/`closed_at` are set only on the corresponding
transition. `CLOSED` is terminal — no reopening exists in the current code.

**Comments** — any ticket participant may add one; only the comment's own
author or a Company Administrator may edit/delete it. Every comment mutation
also writes a `TicketHistory` row.

**Attachments** — anyone who can view the ticket may upload, download, or
delete any attachment on it (no per-attachment ownership layer, unlike
comments). Upload validation is **extension- and size-based**
(`.png/.jpg/.jpeg/.pdf/.txt/.docx/.xlsx`, capped at
`MAX_ATTACHMENT_SIZE_BYTES`), not content-sniffed — see `docs/TECH_DEBT.md`.
The client-supplied filename is shown in the UI but never trusted for
storage; a randomly generated filename is what actually lands on disk.

**History** — every field edit, assignment, status change, comment
add/edit/delete, attachment add/delete, and inventory reserve/consume/
release/undo writes a structured `TicketHistory` row (who, what field, old
value, new value, when) — read-only via `GET /tickets/{id}/history`.

**Deletion** — Company Administrator only. Reverts any `RESERVED`/`CONSUMED`
inventory on the ticket first (writing the corresponding
`InventoryTransaction` rows), then hard-deletes the ticket, which cascades to
its own comments/attachments/history rows. See `docs/TECH_DEBT.md` for the
one known non-atomicity between that inventory revert and the ticket delete
itself.

### Inventory integration (`TicketInventoryService`)

`TicketInventoryUsage` tracks only the **current** ticket↔item relationship
(`RESERVED`/`CONSUMED`); `InventoryTransaction` is the permanent, append-only
audit trail every reserve/release/consume/undo also writes to. See
`docs/database-design.md` §14–15 for the full state machine, the
SERIALIZED/BULK distinction, and the documented V1 limitation on repeated
consumption of the same BULK item on one ticket.

## 13. Company registration

`POST /companies/register` (public) and `POST /platform/companies` (System
Administrator only) both delegate to the same
`CompanyService.register_company` — no parallel creation logic. One
transaction creates:

- The company row (`timezone="UTC"`, `language="en"`).
- Its first Company Administrator (the only role a registration payload can
  produce — Employees/Technicians are always created afterward via `POST
  /users`).
- Starter reference data: 4 priorities (`Low`/`Medium`/`High`/`Critical`), 5
  ticket categories (`Hardware`/`Software`/`Network`/`Account
  Access`/`Other`), 1 location (`"Head Office"`), 1 department
  (`"General"`), and 11 inventory categories (`Laptop`, `Desktop`, `Monitor`,
  `Printer`, `Keyboard`, `Mouse`, `Dock`, `Phone`, `Network Equipment`,
  `Cable`, `Other`).

Only `company_code` is checked for uniqueness during registration (it's the
one value unique platform-wide); usernames/emails need no check, since a
brand-new company starts with zero users. Self-registration signs the new
admin in immediately (`AuthService.issue_tokens`); platform-provisioned
registration does not issue tokens for the new tenant's admin — see §14.

## 14. Platform administration

A System Administrator's console is deliberately a separate service
(`PlatformService`) from `CompanyService`, which owns tenant business logic —
"view across every company" is a fundamentally different operation from "a
Company Administrator managing its own company," not a superset of it.

- `GET /platform/overview` — total/active/inactive company counts, total
  tenant users (never counting the System Administrator's own account), and
  the 5 most recently created companies.
- `GET /platform/companies` — searchable, sortable, paginated company list.
- `GET /platform/companies/{id}` — one company plus its user/ticket/inventory
  aggregate counts.
- `PATCH /platform/companies/{id}/activate` / `.../deactivate` — flips
  `Company.is_active` only; idempotent; every access-control consequence is
  enforced by existing, unmodified auth code (§5), not by this endpoint
  itself.
- `POST /platform/companies` — provisions a new company via
  `CompanyService.register_company`, unchanged (§13).

Every route requires `require_roles("System Administrator")`; a `company_id`
appearing in a URL here identifies the *target* being inspected, never
authorization — access comes exclusively from the role check.

## 15. Analytics

`AnalyticsService` composes `TicketRepository`'s aggregate queries with the
one canonical ownership rule from `TicketService.resolve_ownership_scope`
(§10) — ticket analytics and normal ticket listing can never disagree about
who is allowed to see what, by construction.

**`GET /analytics/tickets`** (Employee/Technician/Company Administrator):
status/priority/category breakdowns, high-priority-open count, a
Company-Administrator-only unassigned count, created-today/resolved-today
counts, average resolution minutes (`null` with zero resolved tickets in
scope, not zero), and a 6-calendar-month created/resolved trend. Every
"today"/"this month" boundary is computed from the caller's **company
timezone** (`Company.timezone`), converted to UTC before comparing against
UTC-basis `created_at`/`resolved_at`.

**`GET /analytics/inventory`** (Technician/Company Administrator — Employee
is refused outright, matching Employee having no inventory access anywhere):
Company Administrator gets the full company-wide picture (total items,
low-stock count, warranty-expiring-within-30-days count, status/category
breakdowns); Technician gets only `reserved_for_my_tickets_count` — a
genuinely narrower response assembled by a different code branch, not the
admin shape with fields hidden downstream.

## 16. Errors, response format, filtering

- Domain exceptions raised by a service are caught in the route and mapped to
  the appropriate HTTP status: `400` (invalid reference/malformed request),
  `403` (permission), `404` (not found), `409` (conflict/invalid state
  transition), `422` (Pydantic validation failure, before the route body ever
  runs).
- List endpoints built from Milestone 5 onward accept `skip`/`limit`
  (`limit` capped at 500) and return a `{data, msg}` `DataResponse`, with
  `msg` including a human-readable "Fetched N of M" count where relevant;
  `/platform/companies` additionally exposes a structured `total` field.
- **Pagination is server-supported but not always server-driven on the
  frontend** — some list pages (e.g. the ticket list) fetch up to the 500-row
  cap in one request and paginate client-side rather than requesting each
  page from the server. See `docs/TECH_DEBT.md`.

## 17. Tests

`backend/tests/` — one file per feature/route group, run with `pytest`. The
suite needs no real database connection: every service accepts its
repository as a swappable constructor argument, and `conftest.py` supplies
small in-memory fakes instead. As of this document, the full suite is 705
tests, passing, plus a clean `ruff check` and a clean `alembic check` (no
model/migration drift). See the root README's "Running tests" section for
exact commands.

## 18. Security review

**Implemented, confirmed in code:**
- Argon2 password hashing (never plaintext, never logged).
- JWT access/refresh tokens with distinct, non-interchangeable `"type"`
  claims and separate expiries.
- Every tenant read/write scoped to the authenticated caller's own
  `company_id`, enforced structurally by `CompanyScopedRepository` (§5).
- Role checks (`require_roles`) plus per-resource ownership checks
  (ticket/comment/inventory-usage) on top of role alone.
- Non-disclosing login errors (§9) — a 401 never reveals which part of the
  credential triple was wrong.
- Upload size caps and extension allow-lists for both ticket attachments and
  company logos; the client-supplied filename is never trusted for on-disk
  storage.
- CORS restricted to an explicit origin allowlist (never `*`/`null`),
  including the Electron app's custom `app://itonit` origin when configured.

**Current V1 limitations (see `docs/TECH_DEBT.md` for the full list and
rationale):** no server-side logout/token revocation; no login rate limiting;
upload validation is extension/size-based, not content-sniffed; no password
reset flow; no frontend automated test suite; the Electron build is unsigned
with no auto-updater.

## 19. Frontend integration

The React frontend (`frontend/`) is a plain Axios client against this API —
see `frontend/README.md` for its own structure. Relevant backend-facing
details:

- **Silent refresh**: `AuthProvider` bootstraps from a stored refresh token
  on load; Axios's response interceptor catches a `401`, calls `POST
  /auth/refresh`, and retries the original request — a page reload never
  forces a full re-login as long as the refresh token is still valid.
- **Logout**: purely client-side (`tokenStore.clear()`) — see §9.
- **Unknown response fields never break the frontend**: Pydantic's
  `extra="ignore"` means a stale client sending a removed field like `theme`
  is never rejected; conversely, the frontend's TypeScript types are kept in
  sync with the schemas by hand, not generated.
- **Role-gated routing**: `AppRouter` and `Sidebar` key their nav/route
  guards off the same four role strings the backend uses
  (`Employee`/`Technician`/`Company Administrator`/`System Administrator`).

## 20. Electron desktop integration

`desktop/` is a separate npm package — a thin Electron **shell**, not a
second implementation of the app. It loads the exact same React bundle
(`frontend/`'s desktop build, `dist-desktop/`) and talks to the same external
FastAPI backend over plain HTTP/JSON; Electron bundles neither FastAPI nor
SQL Server.

- **Dev**: `electron .` loads the Vite dev server directly
  (`http://localhost:5173`, started via `npm run dev:desktop` in
  `frontend/`).
- **Prod** (`electron . --prod`, or the packaged app): a custom `app://`
  protocol handler (`protocol.handle("app", ...)` in `desktop/main.js`)
  serves the built renderer from `frontend/dist-desktop/`, so the SPA's
  client-side routing, root-absolute asset paths, and `localStorage` all
  behave exactly as they do on the web — a plain `file://` origin would break
  all three.
- **Backend CORS**: because the production origin is `app://itonit`, not an
  `http(s)://` origin, the backend's `CORS_ORIGINS` allowlist must include
  that exact string for the packaged app to be able to call the API at all
  (see the root README's environment-variables section).
- **Security posture**: `contextIsolation: true`, `nodeIntegration: false`,
  `sandbox: true` on the `BrowserWindow`; external `http(s)` links open in the
  system browser instead of navigating the app window.
- **Packaging**: `electron-builder`, Windows targets `nsis` (one-click
  installer) and `portable`. The build is **unsigned** (no code-signing
  certificate configured) with **no auto-updater** — see the root README's
  desktop section for the exact build commands and the SmartScreen warning
  this causes.

## 21. Swagger

`GET /docs` (Swagger UI) and `GET /openapi.json` (raw schema) are generated
directly from the route decorators, Pydantic schemas, and docstrings — there
is no hand-maintained OpenAPI file to fall out of sync. Every `response_model`
in the codebase (§8) is what drives the schema shown there.

## 22. End-to-end flow summary

See [`docs/BACKEND_DIAGRAMS.md`](BACKEND_DIAGRAMS.md) for the full set of
Mermaid diagrams this document's narrative corresponds to: overall
architecture, tenant + platform auth flows, the complete ER diagram,
the ticket status state machine, a worked ticket-lifecycle sequence
(including inventory reserve/consume), the attachment upload flow, the
inventory reserve/consume/release/remove flow, the company registration
flow, the platform access-boundary diagram, and the generic
request-processing flow every endpoint follows.
