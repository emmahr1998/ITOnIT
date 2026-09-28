# ITOnIT Backend — Simplified Flow (for presentation)

A shorter, presentation-friendly version of the architecture. For full technical detail with
file/function names for every claim, see `docs/BACKEND_ARCHITECTURE.md` and
`docs/BACKEND_API_GUIDE.md`. Diagrams referenced here live in `docs/BACKEND_DIAGRAMS.md`.

## The one-sentence version

FastAPI receives an HTTP request → CORS-checks the origin → checks who you are (JWT), which
company you belong to, and what you're allowed to do (role/ownership) → validates the JSON
with Pydantic → runs business logic in a Service, scoped to your company → reads/writes SQL
Server through SQLAlchemy → returns a Pydantic-shaped JSON response.

## Starting the server (simplified)

```bash
uvicorn app.main:app --reload
```

1. Python imports `app/main.py`.
2. That import chain pulls in every route → every dependency → every service → every
   repository → every model, and along the way loads `.env` into `Settings`
   (`app/core/config.py`) and prepares (but does not yet open) the SQL Server connection
   (`app/db/database.py`).
3. `FastAPI()` is created, `CORSMiddleware` is attached (allowed origins from
   `CORS_ORIGINS`), and every route is attached (`app.include_router(api_router)`).
4. Uvicorn starts listening. Swagger (`/docs`) is live immediately — no extra step needed,
   FastAPI builds it from the routes that were just registered.

## The complete ticket lifecycle — worked example

Scenario: **Employee Priya**, at a company signed in with code `DEFAULT001`, reports a
broken laptop, and it gets resolved with a hardware swap.

1. **Priya logs in.** `POST /auth/resolve-company {"company_code": "DEFAULT001"}` shows the
   company's name/logo on the login screen, then `POST /auth/login` with her username +
   password + that same company code. Backend verifies the password hash, checks she's
   active and her company isn't suspended, returns an access token + refresh token.
2. **Priya creates a ticket.** `POST /ticket-new` with title `"Laptop does not power on"`,
   `category_id` (Hardware), `priority_id` (High), and a description. She sends her access
   token in the `Authorization` header.
3. **The request schema validates the data.** FastAPI parses the JSON against
   `TicketNewCreate` (`app/schemas/ticket.py`) — title/description non-empty, `category_id`
   and `priority_id` present. If anything's wrong, the request never reaches Priya's code at
   all — it's rejected with `422` automatically.
4. **The backend creates a ticket number.** `TicketService._generate_ticket_number()`
   (`app/services/ticket_service.py`) builds something like `IT-2026-000001` — prefix `IT`,
   current year, a 6-digit sequence number counted from that **company's own** tickets that
   year (another company's tickets don't affect the count).
5. **The backend stores the ticket.** `TicketService._persist_new_ticket` builds a `Ticket`
   row (`status=NEW`, `created_by_user_id=Priya's id`, `assigned_technician_id=None`,
   `company_id=Priya's company`) and saves it through `TicketRepository`.
6. **The backend creates a history record.** In the same operation, a `TicketHistory` row is
   written: `field_name="ticket_created"`, `new_value="IT-2026-000001"`. Both the ticket and
   this history row commit together as one transaction.
7. **Priya uploads an attachment** (a photo of the laptop). `POST
   /tickets/{id}/attachments`, multipart file upload.
8. **The file is saved to disk.** `StorageService.save()` writes it under
   `storage/attachments/` with a randomly generated filename — never the original filename,
   for safety.
9. **Attachment metadata is saved to SQL Server** — the original filename, the stored
   filename, size, content type, and who uploaded it — but not the file's bytes themselves.
   The attachment points only at the ticket (no `comment_id` field exists). Another
   `attachment_added` history row is written.
10. **A Company Administrator assigns a technician.** `PATCH /tickets/{id}/assign` with
    `{"technician_id": ...}`. The backend checks the target user really is an active
    Technician, sets `assigned_technician_id`, and — because the ticket was still `NEW` —
    automatically advances its status to `ASSIGNED` too. Two history rows are written:
    `assigned_technician` and `status`.
11. **The technician changes status.** `PATCH /tickets/{id}/status` with
    `{"status": "IN_PROGRESS"}`. The backend checks this transition is legal
    (`ASSIGNED → IN_PROGRESS` is allowed) and that this technician is the one actually
    assigned. A `status` history row is written.
12. **The technician reserves a replacement part.** `POST /tickets/{id}/inventory
    {"inventory_item_id": ..., "quantity": 1}` — a BULK "Cable"/replacement-part item, say.
    The item's `reserved_quantity` goes up, a `ticket_inventory_usage` row is created, and an
    `inventory_transactions` row (`RESERVED`) plus an `inventory` history row are written.
13. **The technician consumes it.** `PATCH /tickets/{id}/inventory/{usage_id}/consume` —
    `stock_quantity` decrements, the usage row flips to `CONSUMED`, and another
    `inventory_transactions` row (`CONSUMED`) is written.
14. **The technician adds a comment.** `POST /tickets/{id}/comments` — `"Replaced the faulty
    part, laptop powers on now."` A `comment_added` history row is written.
15. **History records everything** — by this point, `GET /tickets/{id}/history` returns a
    complete, ordered timeline: ticket created → attachment added → assigned → status
    changed → inventory reserved → inventory consumed → comment added.
16. **The ticket is resolved.** `PATCH /tickets/{id}/status` with
    `{"status": "RESOLVED"}` (allowed from `IN_PROGRESS`). `resolved_at` is set automatically.
17. **The ticket may later be closed.** `PATCH /tickets/{id}/status` with
    `{"status": "CLOSED"}` (only allowed from `RESOLVED`). `closed_at` is set. `CLOSED` is a
    dead end — the code does not support reopening a closed ticket.

Every one of these steps is one HTTP call to one endpoint, handled by one route function in
`app/api/routes/tickets.py` or `app/api/routes/attachments.py`, which calls one method on
`TicketService`/`AttachmentService`/`CommentService`/`TicketInventoryService`, which calls its
repository, which talks to SQL Server — always scoped to Priya's own company.

## Authentication, simplified

```
pick a company (company code)
   │
   ▼
username + password
   │
   ▼
verify password hash (Argon2) + check is_active + check company is_active
   │
   ▼
issue access token (30 min) + refresh token (7 days)
   │
   ▼
every future request: Authorization: Bearer <access token>
   │
   ▼
backend decodes it, loads the user fresh from the DB (with company + role), checks
role/ownership
   │
   ▼
access token expired? → POST /auth/refresh with the refresh token → new access token
   │
   ▼
logout → frontend clears both tokens locally (no server-side revocation in V1)
```

The one platform-level System Administrator skips the "pick a company" step entirely —
`POST /platform/login` resolves only that one account.

## End-to-end request flow (numbered, matches the diagram)

1. Client sends an HTTP request (JSON or multipart) with a Bearer token.
2. `CORSMiddleware` checks the request's Origin against `CORS_ORIGINS`.
3. FastAPI matches the route by method + path.
4. Dependencies run in order: open a DB session → decode the JWT → load the user (+ company +
   role) → resolve `company_id` for tenant routes → check role/ownership.
5. If any of those fail: 401 (bad/missing/expired token) or 403 (wrong role/not your
   resource/no company) — the route body never runs.
6. Pydantic validates the request body against the route's schema — 422 if invalid (an
   unknown/removed field like a stale `theme` is silently ignored, not rejected).
7. The route calls one Service method.
8. The Service applies business rules and, if something's wrong, raises a specific Python
   exception (e.g. `TicketNotFoundError`).
9. The Service's Repository builds and runs the SQL query/queries via SQLAlchemy, filtered by
   `company_id` automatically for every tenant-owned table.
10. If a mutation happened, the Service writes a `TicketHistory` row (for ticket-related
    changes) and/or an `InventoryTransaction` row (for inventory changes), then commits the
    transaction.
11. If the Service raised an exception, the route catches it and turns it into the right
    HTTP status code.
12. Otherwise, the returned ORM object(s) are serialized through the route's response
    schema — this is also where a nested object (like a ticket's category) gets
    included, and where sensitive fields (like a password hash) get silently dropped because
    the schema never declares them.
13. FastAPI sends the JSON response back to the client.

See `docs/BACKEND_DIAGRAMS.md` for this same flow as a Mermaid sequence diagram.
