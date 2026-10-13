# ITOnIT Backend — Quick Summary (5–10 minute read)

For full detail, see `BACKEND_ARCHITECTURE.md` (deep dive), `BACKEND_API_GUIDE.md`
(endpoint reference), `BACKEND_DIAGRAMS.md` (visuals), `BACKEND_FLOW.md` (worked example),
`database-design.md` (schema), and `PROFESSOR_QA.md` (Q&A). This file is the one to read
right before presenting.

## What it is

A multi-tenant REST API (no server-rendered pages) for IT ticket and inventory
management. Each customer company signs in with its own company code. Employees
report issues; technicians resolve them, optionally reserving/consuming IT
inventory in the process; Company Administrators manage users, reference data,
inventory, and company settings; a single platform-level System Administrator
provisions and oversees companies from outside any one tenant. Every action is
authenticated, permission-checked, and — for tickets — audited.

## Stack

Python, **FastAPI** (routing, validation, auto-generated Swagger), **SQLAlchemy 2.0** (ORM),
**pyodbc** (SQL Server driver), **Alembic** (migrations), **Pydantic v2** (request/response
validation), **PyJWT** (access + refresh tokens), **pwdlib/Argon2** (password hashing),
**python-multipart** (file uploads), **pytest** (705 tests, all passing, as of this writing).

## Architecture in one picture

```
Client (web / Electron desktop / Swagger) → CORS check → FastAPI route
       → auth/role/company-scope dependencies → Pydantic validation
       → Service (business rules) → CompanyScopedRepository (SQL) → SQL Server
       → response schema → JSON
```

Five layers, one direction of dependency: **routes** are thin and only translate HTTP ↔
domain exceptions; **services** own business rules and transactions; **repositories** are the
only place SQL queries are built, and every tenant-owned one filters by `company_id`
automatically; **models** are the tables; **schemas** are what actually
crosses the wire. This separation is why, for example, a password hash can never leak in a
response — no response schema anywhere declares that field — and why one company can never
see another's data even from a bug in a single query.

## Database (15 domain tables + Alembic's own bookkeeping table)

`companies`, `roles`, `users`, `departments`, `priorities`, `categories`, `locations`,
`tickets`, `comments`, `attachments`, `ticket_history`, `inventory_categories`,
`inventory_items`, `inventory_transactions`, `ticket_inventory_usage`. Every foreign key
and unique constraint is enforced at the database level. Ticket cascade deletes
(comments/attachments/history) are enforced at the **application** level (SQLAlchemy ORM
`cascade="all, delete-orphan"`), not `ON DELETE CASCADE` in the database — correct for
everything the app does. See `docs/database-design.md` for the full column-by-column
reference and `docs/TECH_DEBT.md` for known limitations.

## Authentication in one paragraph

Pick a company (by its company code) → log in with username (or email) + password →
backend verifies the Argon2 password hash, that the account is active, and that the
company isn't suspended → issues a short-lived **access token** (30 min) and a
long-lived **refresh token** (7 days), each a signed JWT carrying a `"type"` claim so one
can never be used in place of the other. Every subsequent request sends the access token as
`Authorization: Bearer ...`; when it expires, `POST /auth/refresh` exchanges the refresh
token for a new access token without re-entering credentials. The one platform-level System
Administrator logs in separately, at `POST /platform/login`, with no company code at all.
Logout is client-side only — there is no server-side token revocation in V1.

## Roles, at a glance

| Role | Can do |
|---|---|
| Employee | Create/view own tickets, comment/attach on own tickets, edit own ticket only while still NEW; no inventory access |
| Technician | View/edit/comment/attach on assigned tickets, change status of assigned tickets, reserve/consume/release inventory on assigned tickets |
| Company Administrator | Everything above on *every* company ticket, plus assign technicians, delete tickets, manage users/reference data/inventory, company settings, undo a consumed inventory usage |
| System Administrator | Platform-only: overview, company list/detail, activate/deactivate a company, provision new companies — no access to any tenant's tickets/users/inventory through the normal endpoints |

Any number of Company Administrators may exist per company — it is not a singular role.
There is no "Manager" role and no bare "Administrator" role in the final schema; see
`docs/TECH_DEBT.md` for that consolidation's history.

## Ticket lifecycle

`NEW → ASSIGNED → IN_PROGRESS ⇄ WAITING_FOR_EMPLOYEE → RESOLVED → CLOSED`. `CLOSED` is
terminal — the code does not support reopening. Assignment auto-advances `NEW → ASSIGNED`;
every other transition goes through `PATCH /tickets/{id}/status` and is checked against a
fixed transition table. `resolved_at`/`closed_at` are set automatically on entering those two
statuses.

## Ticket numbers

Format `IT-<year>-<6-digit sequence>`, e.g. `IT-2026-000001` — generated per **company**
(each company's numbering starts independently) by counting existing tickets for the
current year and incrementing. A retry loop handles the rare case of two requests
generating the same number at the same instant.

## History / auditing

Every meaningful ticket change — creation, field edits, assignment, status changes, comments
added/edited/deleted, attachments added/deleted, inventory reserved/consumed/released/undone —
writes one row to `ticket_history` with the old value, the new value, who did it, and when.
One shared function (`HistoryService.record`) is the only place these rows are ever created.
Inventory items separately carry their own permanent, append-only `inventory_transactions`
log, which survives even if the ticket that caused an entry is later deleted.

## Attachments

Uploaded as multipart form data, validated (non-empty, ≤10 MB, extension allow-listed — not
content-sniffed), saved to disk under `storage/attachments/` with a random server-generated
filename (never the original), with only metadata (not the file bytes) stored in SQL Server.
An attachment belongs to exactly one ticket — there is no `comment_id` anywhere in the final
schema. Deleting a ticket also deletes its attachments' physical files, not just the database
rows.

## Locations

A predefined, company-managed list that replaced free-text ticket locations. Deactivated
rather than deleted (`is_active=False`) so historical tickets keep a valid reference — a
ticket can never newly select a deactivated location. Only a Company Administrator can
create/edit/deactivate locations.

## Inventory, in one paragraph

Two tracking types share one `inventory_items` table: **SERIALIZED** (one physical unit per
row — a specific laptop, asset-tag required, the full `AVAILABLE/RESERVED/IN_USE/IN_REPAIR/
RETIRED` status range) and **BULK** (a SKU-level quantity — cables, mice — restricted to
`AVAILABLE`/`RETIRED`, tracked by `stock_quantity`/`reserved_quantity`). A Technician can
reserve an item against an assigned ticket, then consume it (decrementing stock or marking a
serialized unit in-use); only a Company Administrator can undo a consumption. Every one of
those actions writes a permanent `inventory_transactions` row alongside the ticket's own
history entry.

## API shape

Endpoints added from Milestone 5 onward wrap their response as `{"data": ..., "msg": ...}`
(`DataResponse[T]`). A handful of earlier endpoints (`/auth/*`, ticket
detail/patch/assign/status, comments, attachments) return the object/array directly — this
inconsistency is intentional (the wrapper wasn't retrofitted onto already-working endpoints),
not a bug.

## Testing approach

No test database — every service accepts its repository as a swappable constructor argument,
so tests inject in-memory fakes instead of hitting SQL Server. Authentication itself is
tested for real (real JWTs are created and verified); only persistence is faked. Correctness
against the actual, migrated SQL Server schema is verified separately, via `alembic check`
and a manual smoke test before each milestone closes.

## Security — what's solid vs. current V1 limitations

**Solid:** Argon2 password hashing, signed JWTs with distinct access/refresh types,
centralized role checks, per-resource ownership checks, 100% ORM-built queries (no SQL
injection surface), file-upload size/extension validation, git-ignored secrets,
inactive-user/suspended-company enforcement, a real CORS allowlist (never `*`/`null`),
and structural multi-tenant isolation (`CompanyScopedRepository`).

**Current V1 limitations (expected for this stage, documented — not silently missing):** no
server-side logout/token revocation, no login rate limiting, upload validation is
extension/size-based rather than content-sniffed, no password reset flow, no frontend
automated test suite, the Electron build is unsigned with no auto-updater. See
`docs/TECH_DEBT.md` for the full list and rationale.

## Files to know cold before presenting

1. `app/main.py` — the whole app, CORS included, in ~30 lines.
2. `app/api/router.py` — every route group in one place.
3. `app/dependencies/auth.py` — authentication, role checks, and `get_current_company_id`
   (the one place tenant scoping comes from).
4. `app/repositories/base.py` — `CompanyScopedRepository`, the structural multi-tenancy
   guarantee.
5. `app/services/ticket_service.py` — the biggest, most important business-logic file
   (ownership, status workflow, ticket numbering).
6. `app/services/ticket_inventory_service.py` — the reserve/release/consume/undo state
   machine.
7. `app/models/company.py` + `app/models/user.py` + `app/models/ticket.py` — the three most
   connected tables.
8. `app/db/database.py` — engine/session/Base.
9. `alembic/versions/` — how schema changes are made safely; `aa1908b341bb` is the most
   recent (removes the unused `theme` columns).
10. `tests/conftest.py` — how the whole test suite avoids needing a real database.
