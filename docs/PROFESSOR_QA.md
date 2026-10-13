# Questions my professor may ask

Answers are grounded in the actual, final code — file/class/function names are given so any
answer can be verified on the spot. See `docs/BACKEND_ARCHITECTURE.md` and
`docs/database-design.md` for full detail behind any answer.

### 1. Why did you choose FastAPI?
It generates OpenAPI/Swagger documentation automatically from the same type-annotated route
functions and Pydantic models used for validation, has first-class async support, and its
dependency-injection system (`Depends(...)`) is what makes it possible to cleanly separate
authentication, authorization, company scoping, and database-session setup from business
logic without duplicating that code in every route (see `app/dependencies/`).

### 2. Why React?
A component model that maps cleanly onto this app's page/widget structure (one component per
route, shared primitives like `StatCard`/`Modal`), a huge ecosystem (React Router for the
role-gated route tree, Axios for the API client), and — practically — it's what lets the exact
same frontend be reused unmodified as the Electron desktop renderer (see Q29), rather than
building and maintaining two UIs.

### 3. Why SQL Server?
A production-grade relational database with strong constraint/transaction support (foreign
keys, `CHECK` constraints, unique indexes — all used extensively, e.g. the inventory tracking
rules in `app/models/inventory_item.py`), widely used in the kind of enterprise/IT-department
environment this project models, and well supported by SQLAlchemy + `pyodbc` + Alembic.

### 4. Why SQLAlchemy and Alembic instead of `Base.metadata.create_all()`?
`create_all()` can only create tables that don't exist yet — it can't apply a column rename,
backfill data, or drop a column safely. Alembic migrations are reviewable Python scripts,
checked into Git, applied in a defined order, and reversible. This project's own migration
history demonstrates why repeatedly: converting a free-text `users.department` column into a
real `Department` table without losing data, converting `Ticket.priority` from a plain string
into a `Priority` table + FK, and — most recently — `aa1908b341bb`, which drops the unused
`theme` columns after first discovering their SQL-Server-generated default-constraint names
dynamically (a plain `drop_column` alone would have failed).

### 5. How is authentication secured?
Argon2 password hashing (`pwdlib.PasswordHash.recommended()`, `app/core/security.py`) — never
plaintext, never logged. JWT access tokens (short-lived, default 30 min) and refresh tokens
(longer-lived, default 7 days), each carrying a `"type"` claim so one can never be substituted
for the other. Login is company-scoped: `POST /auth/login` takes a `company_code` and looks
the user up *within that company only*; every failure mode (unknown company, unknown user,
wrong password, inactive account) collapses into the identical `401`, so a caller can't use the
response to probe which company codes or usernames exist. A user's role is never trusted from
the token itself — every request re-loads the user fresh from the database (see Q16).

### 6. How are passwords stored?
Argon2 hashing via `pwdlib.PasswordHash.recommended()`. Plaintext is never stored, logged, or
returned in any response. `verify_password` re-hashes the supplied plaintext against the
stored hash's own embedded salt/parameters and compares — the plaintext itself is only ever
held in memory for the duration of that one comparison.

### 7. How is multi-tenancy enforced?
Structurally, not by convention. Every tenant-owned table carries a `company_id`. Every
tenant-scoped repository extends `CompanyScopedRepository` (`app/repositories/base.py`),
which overrides `get_by_id`/`get_all` to always filter by `company_id`, and is constructed
only with the authenticated caller's own `company_id` — resolved by
`get_current_company_id` from their JWT-loaded user row, **never** accepted as a client
parameter anywhere. A cross-company id simply doesn't exist as far as that repository is
concerned — it returns "not found," identical to a genuinely nonexistent id, never a distinct
error that would confirm another company's row exists. This is **application-level scoping**,
not a SQL Server engine feature like Row-Level Security — worth being precise about if asked.

### 8. Why are users deactivated instead of hard-deleted?
Deleting a user would either orphan or cascade-delete every ticket, comment, attachment, and
history row they're attributed to — destroying the exact audit trail the system exists to
keep. `User.is_active = False` (`PATCH /users/{id}`) blocks login and every already-issued
token's continued use of protected routes, while every historical row that references the
user (as creator, technician, commenter, uploader, or history actor) stays intact and
correctly attributed.

### 9. Why do attachments belong to tickets rather than comments?
This was a deliberate final design decision: an attachment is evidence about the *ticket*
(a screenshot of the error, a photo of the broken hardware), not about one specific message
in the conversation. `Attachment` (`app/models/attachment.py`) has a `ticket_id` foreign key
and no `comment_id` column or relationship at all — verify directly against
`docs/database-design.md` §12.1. An earlier design draft did include an optional `comment_id`;
it was never carried into the implementation.

### 10. Why use a Locations table instead of free text?
The same reasoning as Categories/Priorities/Departments: a fixed, company-managed list keeps
data consistent for filtering and reporting, and lets a Company Administrator add new
locations without a code change. `Location.is_active` is genuinely enforced (unlike a purely
decorative flag) — `TicketService._get_location_or_raise` rejects a deactivated location for
*new* selection, while a ticket that already references it is completely unaffected, which is
exactly why deactivation (not deletion) was chosen.

### 11. How does inventory integrate with tickets?
Two tables. `TicketInventoryUsage` represents only the **current** relationship between a
ticket and an inventory item (`RESERVED` or `CONSUMED` — the row is deleted the moment it
stops being true). `InventoryTransaction` is a separate, permanent, append-only audit trail —
one row per business event (reserve/release/consume/undo), never updated or deleted. A
Technician assigned to a ticket can reserve an item, then consume it (decrementing BULK stock,
or marking a SERIALIZED unit `IN_USE` with the ticket's requester as its holder); only a
Company Administrator can undo a consumption. See `docs/database-design.md` §14–15 and
`docs/BACKEND_DIAGRAMS.md` §7 for the full state machine.

### 12. What is the difference between Company Administrator and System Administrator?
Company Administrator is a **per-company** role — any number may exist per company, all with
identical permissions, scoped entirely to their own company's data (`company_id` set on their
user row). System Administrator is a **single, platform-level** account
(`company_id IS NULL`), served by an entirely separate route group (`/platform/...`) and its
own login (`POST /platform/login`, no company code). A System Administrator can see *across*
every company (overview, company list/detail, activate/deactivate, provision) but has **no
access to any tenant's tickets/users/inventory** through the normal tenant endpoints — there
is no code path where `get_current_company_id` succeeds for that account at all.

### 13. Why Electron for the desktop app?
It lets the exact same React application ship as a native-feeling Windows app with no
frontend rewrite — `desktop/` is a thin shell (`desktop/main.js`) that loads the same built
renderer (`frontend/dist-desktop/`) the web build produces, just from a different origin. It
was the pragmatic choice for "same app, another distribution channel" given the project was
already a React SPA.

### 14. Does Electron contain the backend or the database?
No. `desktop/main.js` creates a `BrowserWindow` and loads the frontend — it starts no Python
process and no database server. The desktop app talks to an ITOnIT backend running elsewhere
over plain HTTP/JSON, exactly like the web build does; the only backend-facing difference is
that its production origin is the custom `app://itonit` protocol instead of `http://
localhost:5173`, which is why that exact origin must be added to the backend's `CORS_ORIGINS`
allowlist for the packaged app to work at all.

### 15. How is analytics scoped?
`AnalyticsService` never re-derives its own visibility rule — it calls the identical
`TicketService.resolve_ownership_scope` normal ticket listing uses, so `GET /analytics/tickets`
can never show a different set of tickets than `GET /all-tickets` would for the same user.
Company Administrator gets the full company-wide picture; Technician's numbers are computed
only over tickets assigned to them; Employee's only over tickets they created. Inventory
analytics is narrower still: Employee has no inventory access at all (refused outright), and
Technician gets a single scoped number (`reserved_for_my_tickets_count`) rather than the
company-wide breakdowns Company Administrator sees.

### 16. How do you know a user's role without storing it in the JWT?
The JWT only carries `sub` (user id), `type`, `iat`, `exp` — no role or company. `get_current_user`
(`app/dependencies/auth.py`) looks the user up fresh from the database on *every* request via
`UserRepository.get_by_id` (which also eager-loads their company and role). This means a role
change, a deactivation, or a company suspension takes effect on the very next request, not
just after the token expires — a deliberate trade-off of one extra DB lookup per request for
correctness.

### 17. Why separate SQLAlchemy models and Pydantic schemas instead of using the model directly as the API shape?
A model represents *storage* (every column, including `User.password_hash`). A schema
represents *one specific HTTP message*. Because no response schema in `app/schemas/`
declares `password_hash`, it is structurally impossible to leak it — not because someone
remembered to filter it, but because the field doesn't exist on the schema that serializes
the response.

### 18. How are permissions enforced?
Two layers. Role-based: `require_roles(*names)` (`app/dependencies/auth.py`), a single
factory function every route-level role check goes through — never duplicated inline.
Ownership-based: individual services (`TicketService._ensure_can_view`,
`CommentService`'s author check, `TicketInventoryService`'s assigned-technician check,
`UserService`'s self-vs-admin field split) enforce "is this *specific* resource yours" beyond
what a role alone can express.

### 19. What happens if a database transaction fails?
Repositories never call `commit()` — only `add`/`flush`/`delete`. The owning Service calls
`commit()` once, after every step of one logical operation has succeeded. If a database
constraint is violated mid-operation (e.g. a race on a unique `ticket_number` or
`company_code`), the service catches `IntegrityError`, calls `self._db.rollback()`, and either
retries (ticket-number generation, up to 3 attempts) or re-raises its own domain exception
(e.g. `CompanyCodeConflictError`), which the route turns into a 409.

### 20. Why does `username` also accept an email address at login?
`UserRepository.get_by_username_or_email()` runs one query that matches either column, within
the resolved company. This was a deliberate compatibility decision: the API documents a single
login field (`username`), but an account identified only by email still works, without adding
a second documented login parameter.

### 21. How is SQL injection prevented?
Every single query in `app/repositories/` is built with SQLAlchemy's `select()` query builder
and bound parameters — user input is never string-formatted into SQL. The only raw SQL
(`op.execute(...)`) anywhere in the codebase lives inside Alembic migration scripts (e.g.
discovering and dropping a SQL-Server-generated default-constraint name in `aa1908b341bb`),
used for one-time schema-migration operations with no user-controlled input, never in a
request-serving code path.

### 22. What's the difference between 401 and 403 in this API?
401 means "I don't know who you are" — missing, malformed, expired, or wrong-type token, or an
inactive user. 403 means "I know who you are, but you're not allowed to do this" — wrong role
(`require_roles`), an ownership violation (e.g. a Technician trying to view a ticket not
assigned to them), or a company-less account (the System Administrator) hitting a tenant-only
route.

### 23. Is there any protection against uploading a malicious file?
Extension allow-listing (`.png/.jpg/.jpeg/.pdf/.txt/.docx/.xlsx`) and a size cap, both in
`AttachmentService.upload_attachment`, plus a randomly generated on-disk filename (the
client's filename is never trusted for storage) and path-traversal defense in
`StorageService`. There is **no content scanning** — a file whose actual content doesn't match
its extension would pass validation based on the extension alone. This is a documented,
current V1 limitation, not an oversight — see `docs/TECH_DEBT.md`.

### 24. What testing strategy did you use, and why no real test database?
Every `Service` accepts its repository as an optional constructor argument
(`repository: XRepository | None = None`), defaulting to the real, SQLAlchemy-backed one.
Tests (`tests/conftest.py`) inject small, hand-written in-memory fake repository classes
instead — same method signatures, backed by plain Python dicts. This makes the full suite
(705 tests, as of this writing) run without a database dependency, while still exercising
real HTTP routing, real JWT creation/validation, and the real business-rule code paths.
Correctness against the actual, migrated SQL Server schema is verified separately, via
`alembic check` and a manual smoke test before each milestone closes.

### 25. What would you improve in a production V2?
See `docs/TECH_DEBT.md` for the full, current list — in short: server-side token revocation
(so logout is real, not just client-side), rate limiting on login, content-based upload
validation instead of extension/size alone, a password-reset flow, an automated
frontend test suite, server-driven pagination everywhere (some lists currently fetch up to
500 rows and paginate client-side), code signing and an auto-updater for the Electron build,
and lifting the current one-consumption-per-ticket-per-BULK-item limitation once
`InventoryTransaction`'s full event history can back a richer usage model.
