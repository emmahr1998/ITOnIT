# ITOnIT Backend — API Guide

Endpoint-by-endpoint reference for the final API surface, derived directly
from `app/api/routes/*.py` and `app/api/router.py` — not reconstructed from
memory. Every method, path, and role requirement below matches the route
decorators exactly. For a live, always-in-sync view, use Swagger UI
(`GET /docs`) while the server is running. This guide does not reproduce
every Pydantic field of every schema; see `app/schemas/*.py` (or Swagger) for
exact request/response shapes when a field-level answer is needed.

**Roles:** `Employee`, `Technician`, `Company Administrator` (any number per
company), `System Administrator` (one, platform-level, `company_id IS NULL`).
"Authenticated" below means any active, logged-in user of any role, unless a
specific role list is given. Every tenant route's `company_id` comes from the
caller's own JWT-resolved user row — never from the client.

---

## Health

### `GET /health`
Public. Verifies the database with a live query. Returns `{status}`.

### `GET /`
Public. `{"message": "Welcome to ITOnIT!"}`.

---

## Authentication (`/auth`)

### `POST /auth/resolve-company`
Public. Body: `{company_code}`. Looks up a company by its code for the login
screen. `404` if unknown, `403` if suspended. Returns
`{company_name, company_logo}`.

### `POST /auth/login`
Public. Body: `{company_code, username, password}` (`username` matches
either the username or email column). Returns `{access, refresh,
token_type}`. `401` for any credential failure (deliberately
indistinguishable), `403` if the company is suspended.

### `POST /auth/refresh`
Public (requires a valid refresh token in the body, not a bearer header).
Body: `{refresh}`. Returns a new `{access, token_type}`. `401` if the token
is invalid, expired, the wrong type, or its user is missing/inactive.

### `GET /auth/me`
Authenticated. Returns the caller's own profile
(`CurrentUserResponse` — no `password_hash`, no `theme`).

---

## Companies (`/companies`) — self-service, own company only

### `POST /companies/register`
Public. Body: company name/code + the first admin's own
name/email/username/password. Creates the company, its first Company
Administrator, and starter reference data in one transaction (see
`docs/BACKEND_ARCHITECTURE.md` §13), then returns `{access, refresh,
token_type}` — the new admin is signed in immediately. `409` if
`company_code` is already taken.

### `GET /companies/me`
Company Administrator only. Returns the caller's own company's settings
(`id, name, company_code, contact_email, logo_url, timezone, language`) —
**no `theme` field**.

### `PATCH /companies/me`
Company Administrator only. Partial update of `name`/`company_code`/
`contact_email`. Changing `company_code` immediately affects sign-in for
everyone at the company. `409` on a code conflict.

### `POST /companies/me/logo`
Company Administrator only. Multipart file upload (`.png`/`.jpg`/`.jpeg`/
`.webp`, ≤ `MAX_LOGO_SIZE_BYTES`). `400` on an empty/oversized/unsupported
file.

### `GET /companies/{company_id}/logo`
Public, unauthenticated — a company's own logo isn't sensitive, and the
pre-login screen needs to render it. `404` if the company or its logo
doesn't exist.

---

## Platform (`/platform`) — System Administrator only, except login

### `POST /platform/login`
Public. Body: `{username, password}` — no `company_code`; resolves only the
one platform-level account. `401` for any failure (same non-disclosure
contract as tenant login).

### `POST /platform/companies`
System Administrator only. Same body as `POST /companies/register`; delegates
to the identical registration logic. Unlike self-registration, **no tokens
are returned** — the System Administrator is never signed in as the new
tenant's admin. `409` on a code conflict.

### `GET /platform/overview`
System Administrator only. `{total_companies, active_companies,
inactive_companies, total_users, recent_companies}` (5 most recent).

### `GET /platform/companies`
System Administrator only. Query params: `search`, `is_active`, `sort_by`,
`sort_dir`, `skip`, `limit` (≤ 500). Returns a page of company summaries plus
a structured `total`.

### `GET /platform/companies/{company_id}`
System Administrator only. One company plus `user_count`, `ticket_count`,
`inventory_item_count`. `404` if the id doesn't exist.

### `PATCH /platform/companies/{company_id}/activate` / `.../deactivate`
System Administrator only. Idempotent; flips only `Company.is_active`. `404`
if the id doesn't exist.

---

## Analytics (`/analytics`)

### `GET /analytics/tickets`
Employee, Technician, Company Administrator. Scoped identically to normal
ticket visibility (§10 of the architecture doc). Returns status/priority/
category breakdowns, `high_priority_open_count`, `unassigned_count`
(Company-Administrator-only, else `null`), `created_today`/`resolved_today`,
`avg_resolution_minutes` (`null` with no resolved tickets in scope), and a
6-month `monthly_trend`.

### `GET /analytics/inventory`
Technician, Company Administrator (Employee refused, `403`). Company
Administrator gets the full company-wide picture; Technician gets only
`reserved_for_my_tickets_count`, every other field `null`.

---

## Reference data

### Categories (`/categories`) — ticket categories
- `GET /categories`, `GET /categories/{id}` — Employee, Technician, Company
  Administrator.
- `POST /categories`, `PUT /categories/{id}`, `DELETE /categories/{id}` —
  Company Administrator only. `409` on a name conflict; `DELETE` is refused
  (`409`) if any ticket still references the category — the one reference
  resource with a real hard delete.

### Departments (`/departments`)
- `GET /departments`, `GET /departments/{id}` — any authenticated user.
- `POST /departments`, `PATCH /departments/{id}` — Company Administrator
  only. `409` on a title conflict. **No delete endpoint** — a department can
  be renamed but never removed or deactivated.

### Priorities (`/priorities`)
- `GET /priorities`, `GET /priorities/{id}` — any authenticated user.
- `POST /priorities`, `PATCH /priorities/{id}` — Company Administrator only.
  Same shape/limits as Departments — no delete endpoint.

### Locations (`/locations`)
- `GET /locations`, `GET /locations/{id}` — any authenticated user.
- `POST /locations`, `PATCH /locations/{id}` — Company Administrator only
  (`is_active` toggled via `PATCH`, not a separate endpoint). No hard-delete
  endpoint — a retired location is deactivated, not removed, so tickets that
  already reference it stay valid.

### Inventory Categories (`/inventory-categories`)
- `GET`, `GET /{id}` — Technician, Company Administrator (Employee has no
  inventory access at all).
- `POST`, `PATCH /{id}` — Company Administrator only. No delete endpoint —
  deactivate instead.

---

## Inventory

### Inventory Items (`/inventory-items`)

- `GET /inventory-items` — Technician, Company Administrator. Rich filter
  set: `inventory_category_id`, `tracking_type`, `status`, `condition`,
  `current_location_id`, `current_holder_user_id`, `manufacturer`, `model`,
  `search`, `low_stock` (stock at/below `minimum_stock`),
  `warranty_expiring_days`, plus `sort_by`/`sort_dir`/`skip`/`limit` (≤ 500).
- `GET /inventory-items/{id}` — same roles.
- `POST /inventory-items` — Company Administrator only. Body includes
  `tracking_type` (`SERIALIZED`/`BULK`, immutable after creation),
  `inventory_category_id`, `name`, and the tracking-type-specific fields
  (`asset_tag` required for SERIALIZED, `stock_quantity`/`minimum_stock` for
  BULK, plus optional manufacturer/model/serial/location/holder/
  purchase-and-warranty metadata). `400` for an invalid/inactive category or
  location/holder reference or a tracking-type rule violation; `409` on an
  `asset_tag` conflict.
- `PATCH /inventory-items/{id}` — Company Administrator only. Partial update;
  `tracking_type` cannot be changed after creation (retire and re-create
  instead).
- `GET /inventory-items/{id}/transactions` — Technician, Company
  Administrator. Read-only, paginated history for one item — no
  POST/PATCH/DELETE exists for a transaction row anywhere; every row is
  written internally as a side effect of the endpoints above and of the
  ticket-inventory actions below.

### Inventory Transactions (`/inventory-transactions`)

### `GET /inventory-transactions`
Company Administrator only — a company-wide feed (not scoped to one item),
a step up in scope from the per-item history above. Filters:
`inventory_item_id`, `ticket_id`, `transaction_type`,
`performed_by_user_id`, plus pagination.

### Ticket ↔ Inventory (nested under `/tickets/{ticket_id}/inventory`)

Technician (must be the ticket's assigned technician) or Company
Administrator only — Employee never reaches these routes regardless of
ticket ownership.

- `GET /tickets/{id}/inventory` — list current usage rows for the ticket.
- `POST /tickets/{id}/inventory` — body `{inventory_item_id, quantity}`;
  reserve an item (or merge into an existing BULK reservation). `400`/`409`
  for a not-found/retired/deactivated-category/unavailable/
  insufficient-stock/already-attached item.
- `PATCH /tickets/{id}/inventory/{usage_id}/consume` — mark a `RESERVED` row
  `CONSUMED`; `409` if it isn't currently `RESERVED` or stock is
  insufficient.
- `PATCH /tickets/{id}/inventory/{usage_id}/release` — undo a `RESERVED` row
  (deletes it); `409` if it isn't `RESERVED`.
- `DELETE /tickets/{id}/inventory/{usage_id}` — **Company Administrator
  only.** Undo a `CONSUMED` row (deletes it, reverses stock/status/holder);
  `409` if it isn't `CONSUMED`.

---

## Users (`/users`)

- `POST /users` — Company Administrator only. Creates an Employee,
  Technician, or another Company Administrator on the caller's own company.
  `409` on a username/email conflict; `400` for an invalid `role_id`/
  `department_id`.
- `GET /users` — Company Administrator only. Filters: `role_id`,
  `department_id`, `is_active`, `search`, plus pagination.
- `GET /users/{id}` — any authenticated user, but only for **themselves**
  unless the caller is a Company Administrator (`403` otherwise).
- `PATCH /users/{id}` — a Company Administrator may set any field on anyone
  in their own company; anyone else may only edit **their own** profile, and
  only `first_name`/`last_name`/`phone_number` (any other field in the
  payload is rejected outright, not silently dropped). `409` on a
  username/email conflict.
- `PATCH /users/me/password` — self-service, requires the current password.
  `400` if it's wrong.
- `PATCH /users/{id}/password` — Company Administrator only, sets a user's
  password with no current-password check.

Users are **never hard-deleted** — deactivate via `PATCH .../{id}
{"is_active": false}` instead, preserving every ticket/comment/history
attribution.

---

## Tickets (`/tickets`, plus flat `/ticket-new` and `/all-tickets`)

### `POST /ticket-new`
Employee, Company Administrator. The requester is always the caller unless a
Company Administrator explicitly sets `requester_user_id` to create the
ticket on someone else's behalf (`403` for anyone else attempting that,
`400` if the requester doesn't exist). `400` for an invalid
category/priority/location.

### `GET /all-tickets`
Employee, Technician, Company Administrator. Visibility: Employee sees
tickets they created, Technician sees tickets assigned to them, Company
Administrator sees every company ticket. Full filter set: `status`,
`priority_id`, `category_id`, `department_id`, `requester` (alias for
created-by), `assigned_to`, `search`, `sort_by`, `sort_dir`, `skip`, `limit`
(≤ 500).

### `GET /tickets/{id}`
Any of the three roles, if they can view the ticket (`403`/`404` via
`get_viewable_ticket` otherwise).

### `PATCH /tickets/{id}`
Same view-ownership gate. Partial update of `title`/`description`/
`location_id`/`category_id`/`priority_id` only — assignment, status,
requester, and timestamps each have their own endpoint/mechanism. An
Employee may only edit while the ticket is still `NEW` (`409` afterward); a
Technician may edit once assigned regardless of status; a Company
Administrator always may.

### `DELETE /tickets/{id}`
Company Administrator only. Reverts any inventory on the ticket first, then
hard-deletes it (cascading comments/attachments/history).

### `PATCH /tickets/{id}/assign`
Company Administrator only. Body: `{technician_id}`. `400` if the target
isn't an active Technician, or the ticket is `CLOSED`. Auto-transitions
`NEW → ASSIGNED`.

### `PATCH /tickets/{id}/status`
Technician (must be assigned) or Company Administrator. Body: `{status}`.
`409` for a transition not allowed from the current status (see the state
machine in `docs/BACKEND_DIAGRAMS.md`).

### Comments — `GET`/`POST /tickets/{id}/comments`, `PUT`/`DELETE /tickets/{id}/comments/{comment_id}`
Same view-ownership gate as the ticket itself for read/add; edit/delete is
further restricted to the comment's own author or a Company Administrator.

### History — `GET /tickets/{id}/history`
Read-only, same view-ownership gate.

### Ticket-scoped inventory — see the "Ticket ↔ Inventory" subsection above.

---

## Attachments (`/tickets/{ticket_id}/attachments`)

Own router (not folded into `tickets.py`), same `ticket_id` prefix.

- `GET /tickets/{id}/attachments` — anyone who can view the ticket.
- `POST /tickets/{id}/attachments` — multipart upload; any authenticated user
  who can view the ticket. `400` for an empty/oversized/disallowed-extension
  file (see the allow-list in `docs/BACKEND_ARCHITECTURE.md` §12).
- `GET /tickets/{id}/attachments/{attachment_id}` — downloads the file, with
  a safely encoded `Content-Disposition` header carrying the *original*
  filename (the random on-disk name is never exposed).
- `DELETE /tickets/{id}/attachments/{attachment_id}` — anyone who can view
  the ticket (no per-attachment ownership layer — unlike comments).
