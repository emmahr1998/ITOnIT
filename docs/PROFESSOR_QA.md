# Questions my professor may ask

Answers are grounded in the actual code — file/class/function names are given so any answer
can be verified on the spot. See `docs/BACKEND_ARCHITECTURE.md` for full detail behind any
answer.

### 1. Why did you choose FastAPI?
It generates OpenAPI/Swagger documentation automatically from the same type-annotated route
functions and Pydantic models used for validation, has first-class async support, and its
dependency-injection system (`Depends(...)`) is what makes it possible to cleanly separate
authentication, authorization, and database-session setup from business logic without
duplicating that code in every route (see `app/dependencies/`).

### 2. Why separate SQLAlchemy models and Pydantic schemas instead of using the model directly as the API shape?
A model represents *storage* (every column, including `User.password_hash`). A schema
represents *one specific HTTP message*. Because no response schema in `app/schemas/`
declares `password_hash`, it is structurally impossible to leak it — not because someone
remembered to filter it, but because the field doesn't exist on the schema that serializes
the response.

### 3. Why use Alembic instead of `Base.metadata.create_all()`?
`create_all()` can only create tables that don't exist yet — it can't apply a column rename,
backfill data, or drop a column safely. Alembic migrations are reviewable Python scripts,
checked into Git, applied in a defined order, and reversible. This project's own migration
history demonstrates why: `496ee3278515_add_departments_and_user_profile_fields.py` had to
convert an existing free-text `users.department` column into a real `Department` table
*without losing any data* — something `create_all()` simply cannot do.

### 4. Why use JWT instead of server-side sessions?
JWT is stateless — the server doesn't need to store session data anywhere to validate a
request; it just verifies the token's signature and reads its claims (`app/core/security.py`).
This fits a REST API that a future React frontend will call from the browser without a
shared server-side session store.

### 5. What is the difference between access and refresh tokens in this system?
An access token is short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30 minutes) and is
sent on every authenticated request. A refresh token is long-lived (`REFRESH_TOKEN_EXPIRE_MINUTES`,
default 7 days) and is used *only* to obtain a new access token via `POST /auth/refresh`,
without re-entering credentials. Both carry a `"type"` claim (`"access"` or `"refresh"`) that
`decode_access_token`/`decode_refresh_token` check explicitly — an access token cannot be
used where a refresh token is expected, and vice versa (`app/core/security.py`).

### 6. How are permissions enforced?
Two layers. Role-based: `require_roles(*names)` (`app/dependencies/auth.py`), a single
factory function every route-level role check goes through — never duplicated inline.
Ownership-based: individual services (`TicketService._ensure_can_view`,
`CommentService`'s author check, `UserService`'s self-vs-admin split) enforce "is this
*specific* resource yours" beyond what a role alone can express.

### 7. Why store attachment files outside SQL Server?
Storing large binary blobs in a relational database bloats the database, slows backups, and
wastes the database engine's strengths on something a filesystem does better. `Attachment`
(`app/models/attachment.py`) stores only metadata and a `file_path`; the actual bytes live
under `storage/attachments/`, written/read by `StorageService`
(`app/services/storage_service.py`).

### 8. How do you prevent an employee from assigning a technician?
`PATCH /tickets/{id}/assign` is gated by `require_roles("Manager", "Administrator")`
(`_ASSIGN_ROLES` in `app/api/routes/tickets.py`) — an Employee's request never even reaches
`TicketService.assign_technician`; it's rejected with 403 at the dependency layer.

### 9. How is ticket history implemented?
A dedicated `TicketHistory` table (`app/models/ticket_history.py`), one row per field-level
change: `field_name`, `old_value`, `new_value`, who changed it, when. `HistoryService.record()`
(`app/services/history_service.py`) is the single method that ever constructs a row —
`TicketService`, `CommentService`, and `AttachmentService` all call it, rather than each
writing history rows independently.

### 10. What happens if a database transaction fails?
Repositories never call `commit()` — only `add`/`flush`/`delete`. The owning Service calls
`commit()` once, after every step of one logical operation has succeeded. If a database
constraint is violated mid-operation (e.g. a race on a unique `ticket_number`), the service
catches `IntegrityError`, calls `self._db.rollback()`, and either retries (ticket-number
generation, up to 3 attempts) or re-raises its own domain exception (e.g.
`CategoryNameConflictError`), which the route turns into a 409.

### 11. How would you scale this system?
The most direct paths, given the current architecture: run multiple stateless FastAPI/
uvicorn workers behind a load balancer (the app holds no in-process session state — every
request re-authenticates via JWT), add a connection pool tuned for concurrency, add caching
for read-heavy, rarely-changing data (categories, departments, priorities), and move
attachment storage to a shared/object store so it isn't tied to one server's local disk (see
Q17).

### 12. What would you change before production?
See the "Security review" section of `docs/BACKEND_ARCHITECTURE.md` §22 — in short: add
HTTPS termination, token revocation, rate limiting on login, malware scanning for uploads,
move attachments to cloud/object storage, add structured logging/monitoring, add
`CORSMiddleware` (currently completely absent from `app/main.py`), and move secrets into a
managed secret store instead of a local `.env` file.

### 13. Why does `username` also accept an email address at login?
`UserRepository.get_by_username_or_email()` (`app/repositories/user.py`) runs one query that
matches either column, case-insensitively. This was a deliberate compatibility decision: the
API documents a single login field (`username`), but existing accounts that were only ever
identified by email still work, without adding a second documented login parameter.

### 14. Why is `PATCH /tickets/{id}` different from `PUT /categories/{id}`?
`PATCH /tickets/{id}` (`app/schemas/ticket.py`'s `TicketPatch`) is a **partial** update —
every field is optional, and only the fields actually present in the request are changed.
`PUT /categories/{id}` (`CategoryUpdate`) is a **full replacement** — both `name` and
`description` must be sent every time, because `PUT` semantics mean "this is now the
complete representation of the resource." The project intentionally uses `PATCH` for the
newer ticket-editing endpoint and kept `PUT`'s full-replacement semantics on the
pre-existing category endpoint.

### 15. Why doesn't the response format look the same on every endpoint?
Newer endpoints (Departments, Priorities, Users, `POST /ticket-new`, `GET /all-tickets`,
`PATCH /tickets/{id}`) return a `{"data": ..., "msg": ...}` envelope
(`app/schemas/response.py`'s `DataResponse[T]`). Older, pre-existing endpoints (Categories,
Comments, Attachments, History, `GET /tickets/{id}`, `assign`, `status`, Auth) return the
object/array directly. This was a deliberate choice, documented in the schema's own
docstring, not to retrofit the wrapper onto working endpoints just for consistency's sake.

### 16. How do you know a user's role without storing it in the JWT?
The JWT only carries `sub` (user id), `type`, `iat`, `exp` — no role or name.
`get_current_user` (`app/dependencies/auth.py`) looks the user up fresh from the database on
*every* request via `UserRepository.get_by_id`. This means a role change or account
deactivation takes effect on the very next request, not just after the token expires — a
deliberate trade-off of one extra DB lookup per request for correctness.

### 17. Why is the file storage local disk instead of cloud storage?
Simplicity for a university project — `StorageService` (`app/services/storage_service.py`)
is a small, self-contained class with `save`/`load`/`delete`/`generate_stored_filename`
methods. Because `AttachmentService` only ever calls those four methods, swapping in an
S3/Azure-Blob-backed implementation later would not require changing any calling code — it's
listed explicitly as a needed change before real production deployment.

### 18. How is SQL injection prevented?
Every single query in `app/repositories/` is built with SQLAlchemy's `select()` query
builder and bound parameters — user input is never string-formatted into SQL. The only raw
SQL (`op.execute(...)`) anywhere in the codebase lives inside Alembic migration scripts, used
for one-time schema-migration data backfills with no user-controlled input, never in a
request-serving code path.

### 19. How are passwords protected?
Argon2 hashing via `pwdlib.PasswordHash.recommended()` (`app/core/security.py`). Plaintext is
never stored, logged, or returned in any response. `verify_password` re-hashes the supplied
plaintext against the stored hash's own embedded salt/parameters and compares — the
plaintext itself is only ever held in memory for the duration of that one comparison.

### 20. What's the difference between 401 and 403 in this API?
401 means "I don't know who you are" — missing, malformed, expired, or wrong-type token, or
an inactive user (`app/dependencies/auth.py`). 403 means "I know who you are, but you're not
allowed to do this" — wrong role (`require_roles`) or an ownership violation (e.g. a
Technician trying to view a ticket not assigned to them, `TicketPermissionError`).

### 21. How does the system decide which tickets an Employee can see?
`TicketService.list_tickets` (`app/services/ticket_service.py`) forcibly overwrites the
`created_by` filter with the caller's own id for anyone who isn't a Technician or a
Manager/Administrator — regardless of what filter value the client sent in the query string.
This is server-enforced, not client-trusted, confirmed by a dedicated test
(`test_all_tickets_employee_cannot_bypass_scope_via_filter`).

### 22. Why do Managers see all tickets but can't edit other users?
Two different, independently-designed authorization rules: ticket visibility is checked in
`TicketService._is_manager_or_admin` (both Manager and Administrator bypass ownership
scoping), while user-editing is checked in `UserService.update_user` against a stricter
`current_user.role.name == "Administrator"` check specifically. This means a Manager has
broad *read* access across tickets but no special *write* access to other users' accounts —
only an Administrator can edit someone else's account. This is a real, intentional asymmetry
in the current permission design, worth being able to explain if asked why it isn't
symmetric.

### 23. What testing strategy did you use, and why no real test database?
Every `Service` accepts its repository as an optional constructor argument
(`repository: XRepository | None = None`), defaulting to the real, SQLAlchemy-backed one.
Tests (`tests/conftest.py`) inject small, hand-written in-memory `Fake*Repository` classes
instead — same method signatures, backed by plain Python dicts. This makes the 250-test suite
run in seconds with no database dependency, while still exercising real HTTP routing, real
JWT creation/validation, and the real business-rule code paths.

### 24. How do you verify the tests actually reflect the real database schema?
Separately from `pytest` — via `alembic check` (confirms the SQLAlchemy models match the
live database with no pending schema drift) and a manual smoke test against the real,
migrated SQL Server database (login, refresh, create a department/priority/user/ticket
through the actual running app, then clean up the test data). This is documented as a
deliberate two-track verification approach: fast, DB-free unit/integration tests for logic
correctness, plus a slower, real-DB pass for schema correctness.

### 25. Why does `Ticket.priority` no longer exist as a plain enum column?
It was replaced by a `Priority` table and a `priority_id` foreign key
(migration `b8c5e972dfbf_add_priorities_table_and_migrate_ticket_.py`) so priorities can be
added, renamed, or reordered by a Manager/Administrator through the API
(`POST /priorities`, `PATCH /priorities/{id}`) without a code change or a new deployment —
the same reasoning applies to why `Department` replaced a free-text `users.department`
string column.

### 26. What happens if two people try to create a ticket at the exact same time?
`TicketService._persist_new_ticket` wraps the insert in a retry loop (max 3 attempts): if the
computed `ticket_number` collides with one another concurrent request just inserted (caught
as a database `IntegrityError` on the unique constraint), it rolls back and generates a new
number before retrying — rather than letting the second request fail outright.

### 27. Why can't a closed ticket be reopened?
`TicketService._STATUS_TRANSITIONS[TicketStatus.CLOSED]` is an empty `frozenset()` — no
status is a legal next step from `CLOSED` in the current business rules. This is a real,
current limitation of the code, not an oversight in this documentation — if the team wants
reopening later, it would need a new transition added to that dictionary plus a role
decision about who's allowed to do it.

### 28. Does deleting a ticket delete its comments and attachments too?
Yes — `Ticket.comments`, `Ticket.attachments`, and `Ticket.history` are all declared with
`cascade="all, delete-orphan"` in `app/models/ticket.py`, so `DELETE /tickets/{id}`
(Manager/Administrator only) permanently removes the ticket and everything attached to it,
including its physical attachment files being orphaned on disk (the DB rows are deleted, but
nothing currently deletes the corresponding files from `storage/attachments/` — a gap worth
mentioning if asked about it directly).

### 29. Is there any protection against uploading a malicious file?
Extension allow-listing and a size cap, both in `AttachmentService.upload_attachment`
(`app/services/attachment_service.py`), plus path-traversal defense in `StorageService`
(rejecting any filename that would resolve outside the storage root). There is **no content
scanning** — a `.png` file that is actually something else in disguise would pass validation
based on its extension alone. This is explicitly listed as a pre-production gap.

### 30. How would a React frontend actually talk to this backend today, as-is?
It can call every endpoint exactly as documented in `docs/BACKEND_API_GUIDE.md` — but one
concrete blocker exists right now: `app/main.py` registers no `CORSMiddleware`, so a browser
running React on a different origin (e.g. `localhost:3000`) would have its requests blocked
by the browser's same-origin policy until CORS is configured. See
`docs/BACKEND_ARCHITECTURE.md` §23 for the full integration walkthrough.
