# ITOnIT Database Design

## 1. Document Introduction

**Document title:** ITOnIT Database Design
**Project name:** ITOnIT

ITOnIT is a multi-tenant IT service/ticket and inventory management system. Each
customer organization (a "company") gets its own isolated slice of data: employees
submit support tickets, technicians resolve them (optionally reserving and
consuming IT inventory in the process), and Company Administrators manage users,
reference data, and inventory for their own company. A separate, platform-level
System Administrator role provisions and oversees companies from outside any one
tenant.

This document describes the **final, as-built** schema — Microsoft SQL Server,
implemented with **SQLAlchemy 2.x** ORM models and versioned exclusively through
**Alembic** migrations. It reflects the schema after migration `aa1908b341bb`
(the most recent one, which drops the last remnants of an unused `theme`
concept). No table in this document is aspirational; every column, constraint,
and relationship listed here exists in the current models and has been verified
against a running SQL Server database.

Tables are **never** created or altered manually in SQL Server Management Studio
(SSMS). Every schema change goes through a reviewed Alembic migration script in
`backend/alembic/versions/`.

---

## 2. Main Entities

The database contains **15 application tables** (plus Alembic's own bookkeeping
table, `alembic_version`, which this document does not describe):

1. `companies`
2. `roles`
3. `users`
4. `departments`
5. `priorities`
6. `categories`
7. `locations`
8. `tickets`
9. `comments`
10. `attachments`
11. `ticket_history`
12. `inventory_categories`
13. `inventory_items`
14. `inventory_transactions`
15. `ticket_inventory_usage`

Every table below other than `companies` and `roles` carries a `company_id`
foreign key (directly, or denormalized from its parent — see §7, Multi-Tenancy).
Timestamp columns are `DATETIME2(3)` (millisecond precision), generated in
application code as naive UTC (see §7's UTC timestamp note) — never the SQL
Server session's local time.

---

## 3. Companies Table

**Table name:** `companies`

**Purpose:** The tenant boundary. One row per customer organization using
ITOnIT. Every other tenant-owned row, directly or indirectly, belongs to
exactly one company.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `name` | `VARCHAR(200)` | No | — | Display name |
| `company_code` | `VARCHAR(20)` | No | — | **Unique platform-wide** (not just per company) — typed at login to select the tenant |
| `logo_path` | `VARCHAR(500)` | Yes | — | Stored filename of an uploaded logo, on disk under `LOGO_STORAGE_PATH`; `NULL` until one is uploaded |
| `contact_email` | `VARCHAR(255)` | Yes | — | |
| `timezone` | `VARCHAR(50)` | No | `'UTC'` | IANA-style name; backs every "today"/"this month" analytics boundary (§7) |
| `language` | `VARCHAR(10)` | No | `'en'` | Stored, not yet used to localize anything in the UI |
| `is_active` | `BIT` | No | `1` | Suspending a company (System Administrator only) blocks new logins and every already-authenticated request, without touching any tenant data |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Primary key:** `id`. **Unique constraint:** `company_code`.

**Delete behavior:** companies are never deleted through the API — only
deactivated (`is_active = 0`) or reactivated by a System Administrator.

---

## 4. Roles Table

**Table name:** `roles`

**Purpose:** The fixed set of permission levels. Every user has exactly one
role.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `name` | `VARCHAR(30)` | No | — | Unique |
| `description` | `VARCHAR(255)` | Yes | — | |

**Seeded records (exactly four, platform-wide, not company-owned):**

- `Employee`
- `Technician`
- `Company Administrator`
- `System Administrator`

There is no "Manager" role and no "Administrator" role in the final schema —
those names existed only in early design drafts and were consolidated before
implementation (see `docs/TECH_DEBT.md`). `roles` has no `company_id`: it is
shared platform vocabulary, identical for every company.

**Relationship:** one role has many users (`roles` 1—* `users`).

---

## 5. Users Table

**Table name:** `users`

**Purpose:** Every person who signs in: employees, technicians, Company
Administrators, and the one platform-level System Administrator.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | **Yes** | — | `NULL` **only** for the single System Administrator account; every tenant user has one |
| `username` | `VARCHAR(50)` | No | — | Unique per company (not platform-wide) |
| `first_name` / `last_name` | `VARCHAR(100)` | No | — | |
| `email` | `VARCHAR(255)` | No | — | Unique per company (not platform-wide) |
| `password_hash` | `VARCHAR(255)` | No | — | Argon2 (see §10) |
| `phone_number` | `VARCHAR(30)` | Yes | — | |
| `department_id` | `INTEGER` FK → `departments.id` | Yes | — | |
| `role_id` | `INTEGER` FK → `roles.id` | No | — | |
| `is_active` | `BIT` | No | `1` | Deactivation, never hard delete (§7) |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Primary key:** `id`. **Unique constraints:** `(company_id, username)`,
`(company_id, email)` — composite, not single-column, so the same
username/email may exist in two different companies without conflict. The
login flow always resolves the company (via `company_code`) before it looks a
user up by username/email.

**Delete behavior:** never hard-deleted. Deactivating (`is_active = 0`) blocks
login and every already-authenticated request, while preserving every ticket,
comment, attachment, and history row the user ever created or was attributed
to — an admin editing/deleting a `created_by`'s row is never an option, only
deactivating the account itself.

**Relationships:** created tickets, assigned tickets (as technician),
comments, attachments, ticket-history entries, held inventory items (as
`current_holder`) — all 1—* from `users`.

---

## 6. Departments Table

**Table name:** `departments`

**Purpose:** The organizational department a user may belong to (e.g. IT,
Finance) — informational/filtering metadata, not a permission boundary.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `title` | `VARCHAR(100)` | No | — | |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Unique constraint:** `(company_id, title)`. **No `is_active` column** and
**no DELETE endpoint** — a department, once created, can be renamed but never
deactivated or removed via the API; every registered company starts with one
seeded department, `"General"`.

---

## 7. Priorities Table

**Table name:** `priorities`

**Purpose:** A ticket priority level (Low/Medium/High/Critical, by default) —
**company-owned data**, not a fixed application enum. This is one of the
biggest departures from the original design: priority used to be a hardcoded
string on the ticket itself; it is now its own table so each company can add,
rename, or remove its own priority levels.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `title` | `VARCHAR(50)` | No | — | |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Unique constraint:** `(company_id, title)`. **No `is_active` column** and
**no DELETE endpoint**, same as Departments. Every registered company is
seeded with exactly four starter priorities: `Low`, `Medium`, `High`,
`Critical`.

**Relationship:** one priority has many tickets (`priorities` 1—* `tickets`,
via `tickets.priority_id`, `NOT NULL`).

---

## 8. Categories Table

**Table name:** `categories`

**Purpose:** Classifies **tickets** by the type of issue reported (e.g.
Hardware, Network) — company-owned, not to be confused with Inventory
Categories (§12), which classify hardware assets and are a separate table
entirely.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `name` | `VARCHAR(100)` | No | — | |
| `description` | `VARCHAR(255)` | Yes | — | |
| `is_active` | `BIT` | No | `1` | |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | No `updated_at` |

**Unique constraint:** `(company_id, name)`. **Delete behavior:** the one
reference-data resource with a real `DELETE` endpoint — but it is refused
(`409 Conflict`) if any ticket still references the category; otherwise it is
hard-deleted. Every registered company is seeded with five starter
categories: `Hardware`, `Software`, `Network`, `Account Access`, `Other`.

**Relationship:** one category has many tickets (`categories` 1—* `tickets`,
`tickets.category_id`, `NOT NULL`).

---

## 9. Locations Table

**Table name:** `locations`

**Purpose:** A predefined physical location a ticket can be reported from
(e.g. "Head Office"), chosen from a company-managed list rather than typed
freely as text.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `title` | `VARCHAR(100)` | No | — | |
| `is_active` | `BIT` | No | `1` | |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Unique constraint:** `(company_id, title)`. **No DELETE endpoint** — a
retired location is deactivated (`is_active = 0`), never removed, so a
ticket that already references it keeps a valid, meaningful location even
after an admin retires it from the selectable list; only active locations may
be newly assigned to a ticket or inventory item. Every registered company is
seeded with one starter location, `"Head Office"`.

**Relationships:** one location has many tickets (`locations` 1—0..*
`tickets`, `tickets.location_id`, **nullable** — a ticket may have no
location) and many inventory items (`locations` 1—0..* `inventory_items`,
`inventory_items.current_location_id`, `ON DELETE SET NULL`).

---

## 10. Tickets Table

**Table name:** `tickets`

**Purpose:** The central entity — one row per IT support request, tracked
from submission through resolution.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `ticket_number` | `VARCHAR(30)` | No | — | Human-readable, e.g. `IT-2026-000001` — numbered independently per company, not globally |
| `title` | `VARCHAR(200)` | No | — | |
| `description` | `TEXT` | No | — | |
| `location_id` | `INTEGER` FK → `locations.id` | **Yes** | — | A ticket may have no location |
| `status` | `VARCHAR(30)` (CHECK) | No | — | See allowed values below |
| `priority_id` | `INTEGER` FK → `priorities.id` | No | — | |
| `category_id` | `INTEGER` FK → `categories.id` | No | — | |
| `created_by_user_id` | `INTEGER` FK → `users.id` | No | — | The requester |
| `assigned_technician_id` | `INTEGER` FK → `users.id` | Yes | — | `NULL` until assigned |
| `resolved_at` | `DATETIME2(3)` | Yes | — | Set only on the transition to `RESOLVED` |
| `closed_at` | `DATETIME2(3)` | Yes | — | Set only on the transition to `CLOSED` |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Primary key:** `id`. **Unique constraint:** `(company_id, ticket_number)`.

**Allowed `status` values** (enforced by a `CHECK` constraint,
`ck_tickets_status`, since SQL Server has no native enum type):
`NEW`, `ASSIGNED`, `IN_PROGRESS`, `WAITING_FOR_EMPLOYEE`, `RESOLVED`,
`CLOSED`. The allowed transition graph is: `NEW → ASSIGNED → IN_PROGRESS ⇄
WAITING_FOR_EMPLOYEE`, `IN_PROGRESS → RESOLVED → CLOSED`. `CLOSED` is
terminal.

**Delete behavior:** a Company Administrator may hard-delete a ticket. Doing
so first releases/reverts any inventory reserved or consumed on it (see §15)
and cascades to delete the ticket's own comments, attachments, and history
rows (`cascade="all, delete-orphan"` on all three relationships) — but any
`inventory_transactions` row that referenced the ticket survives, with its
`ticket_id` set to `NULL` (see §14), preserving the inventory audit trail
even after the ticket itself is gone.

**Relationships:** belongs to one company, one category, one priority,
optionally one location; created by one user, optionally assigned to one
technician user; has many comments, attachments, history entries, and
ticket-inventory-usage rows.

---

## 11. Comments Table

**Table name:** `comments`

**Purpose:** The communication thread on a ticket.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | Denormalized from the parent ticket (see §7) |
| `ticket_id` | `INTEGER` FK → `tickets.id` | No | — | |
| `author_user_id` | `INTEGER` FK → `users.id` | No | — | |
| `content` | `TEXT` | No | — | |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |
| `updated_at` | `DATETIME2(3)` | **Yes** | — | `NULL` unless the comment has been edited |

**Delete behavior:** the comment's own author, or any Company Administrator,
may edit or delete it; hard-deleted when removed (no soft-delete flag).
Deleted automatically (cascade) if its parent ticket is deleted.

---

## 12. Attachments Table

**Table name:** `attachments`

**Purpose:** Metadata for a file uploaded to a ticket. The file content
itself lives on disk, never in SQL Server — only its metadata and storage
location are persisted here.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | Denormalized from the parent ticket |
| `ticket_id` | `INTEGER` FK → `tickets.id` | No | — | **The only parent an attachment has** |
| `uploaded_by_user_id` | `INTEGER` FK → `users.id` | No | — | |
| `original_filename` | `VARCHAR(255)` | No | — | Client-supplied name, shown in the UI, **never trusted for storage** |
| `stored_filename` | `VARCHAR(255)` | No | — | Randomly generated, used as the actual on-disk filename |
| `file_path` | `VARCHAR(500)` | No | — | Location under `ATTACHMENT_STORAGE_PATH` |
| `content_type` | `VARCHAR(100)` | Yes | — | Derived from the validated file extension, not the client-supplied header |
| `file_size` | `INTEGER` | No | — | Bytes |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

### 12.1 Professor-specific fact: attachments belong to tickets, not comments

**`attachments` has a `ticket_id` foreign key and no `comment_id` column or
relationship at all.** This is a deliberate, final design decision, not an
oversight: an attachment belongs to exactly one entity — its ticket — never
optionally to a specific comment. Any older design note or diagram showing
`comment_id` on this table describes a pre-implementation draft, not the
schema that was actually built.

**Delete behavior:** the ticket's own participants (anyone who can view the
ticket) may upload, download, or delete any attachment on it — there is no
per-attachment ownership layer the way comments have one. Deleted
automatically (cascade) if the parent ticket is deleted.

---

## 13. Ticket_History Table

**Table name:** `ticket_history`

**Purpose:** A structured, field-level audit trail of every meaningful change
made to a ticket — field edits, assignment, status transitions, comment
add/edit/delete, attachment add/delete, and inventory reserve/consume/
release/undo.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | Denormalized from the parent ticket |
| `ticket_id` | `INTEGER` FK → `tickets.id` | No | — | |
| `changed_by_user_id` | `INTEGER` FK → `users.id` | No | — | |
| `field_name` | `VARCHAR(50)` | No | — | e.g. `status`, `priority`, `assigned_technician`, `inventory` |
| `old_value` / `new_value` | `VARCHAR(255)` | Yes | — | Human-readable values (e.g. names, not raw ids) |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Delete behavior:** never updated or deleted through the API; deleted
automatically (cascade) only if the parent ticket itself is deleted.

---

## 14. Inventory Tables (Milestones 10–12)

Four tables implement IT asset/stock tracking and its integration with
tickets. This is new relative to the original pre-implementation design and
did not exist until Milestone 10.

### 14.1 `inventory_categories`

**Purpose:** Classifies inventory **items** by asset type (Laptop, Monitor,
Cable, …) — a separate table from `categories` (§8), which classifies
**tickets** by issue type. The two are deliberately not the same table.

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement |
| `company_id` | `INTEGER` FK → `companies.id` | No | — |
| `name` | `VARCHAR(100)` | No | — |
| `is_active` | `BIT` | No | `1` |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` |

**Unique constraint:** `(company_id, name)`. Every registered company is
seeded with eleven starter categories: `Laptop`, `Desktop`, `Monitor`,
`Printer`, `Keyboard`, `Mouse`, `Dock`, `Phone`, `Network Equipment`,
`Cable`, `Other`. Deactivating a category blocks it from being newly
assigned to an item, and blocks any item already in that category from being
newly reserved on a ticket.

### 14.2 `inventory_items`

**Purpose:** One row per physical unit or SKU of company-owned IT hardware.
A single table serves **two tracking types** rather than two separate
tables — see §14.2.1.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | |
| `inventory_category_id` | `INTEGER` FK → `inventory_categories.id` | No | — | |
| `current_location_id` | `INTEGER` FK → `locations.id`, `ON DELETE SET NULL` | Yes | — | |
| `current_holder_user_id` | `INTEGER` FK → `users.id`, `ON DELETE SET NULL` | Yes | — | Only meaningful for SERIALIZED items |
| `asset_tag` | `VARCHAR(50)` | Yes* | — | *Required for SERIALIZED |
| `name` | `VARCHAR(200)` | No | — | |
| `manufacturer` / `model` / `serial_number` | `VARCHAR(100)` | Yes | — | |
| `tracking_type` | `VARCHAR(20)` (CHECK) | No | — | `SERIALIZED` \| `BULK` |
| `status` | `VARCHAR(20)` (CHECK) | No | — | See §14.2.1 |
| `condition` | `VARCHAR(20)` (CHECK) | Yes | — | `NEW`/`GOOD`/`FAIR`/`DAMAGED`/`BROKEN` — physical condition, independent of `status` |
| `stock_quantity` | `INTEGER` (CHECK ≥ 0) | No | `1` | Always `1` for SERIALIZED |
| `reserved_quantity` | `INTEGER` (CHECK ≥ 0, ≤ `stock_quantity`) | No | `0` | `0` or `1` for SERIALIZED |
| `minimum_stock` | `INTEGER` | Yes | — | Backs the "low stock" filter/analytics |
| `purchase_date` / `warranty_expiration` | `DATE` | Yes | — | |
| `supplier` | `VARCHAR(150)` | Yes | — | |
| `purchase_cost` | `NUMERIC(12,2)` | Yes | — | |
| `invoice_number` | `VARCHAR(100)` | Yes | — | |
| `image_path` | `VARCHAR(500)` | Yes | — | |
| `notes` | `TEXT` | Yes | — | |
| `created_at` / `updated_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | |

**Indexes/constraints:**
- `ux_inventory_items_company_id_asset_tag` — a **filtered unique index** on
  `(company_id, asset_tag) WHERE asset_tag IS NOT NULL`, not a plain `UNIQUE`
  constraint. SQL Server's plain `UNIQUE` treats `NULL` as a comparable value
  (allowing at most one `NULL` per company), which would incorrectly block
  more than one untagged BULK item per company — the filtered index avoids
  that.
- Eight `CHECK` constraints enforce the tracking-type rules below at the
  database layer as a backstop (the service/schema layer is the primary
  enforcement, with friendlier errors): a SERIALIZED item must have an
  `asset_tag`, `stock_quantity = 1`, and `reserved_quantity IN (0, 1)`; a
  BULK item's `status` must be `AVAILABLE` or `RETIRED` and it may never
  have a `current_holder_user_id`; and `stock_quantity`/`reserved_quantity`
  are always non-negative with `reserved_quantity <= stock_quantity`.

**Delete behavior:** every FK from `inventory_items` is `NO ACTION` except
`current_location_id` and `current_holder_user_id`, both `ON DELETE SET
NULL` — deleting a location or a user clears the item's reference rather
than blocking the delete or cascading. There is no DELETE endpoint for
inventory items at all; an item is retired via `status = RETIRED` instead.

#### 14.2.1 SERIALIZED vs. BULK

- **SERIALIZED** — one physical unit per row (a specific laptop, a specific
  monitor). Requires an `asset_tag`. `stock_quantity` is always `1`,
  `reserved_quantity` is `0` or `1`. The full `status` range applies:
  `AVAILABLE → RESERVED → IN_USE → (IN_REPAIR) → RETIRED` (not a strict
  linear machine — an item can return to `AVAILABLE` from `RESERVED` or
  `IN_USE`). `current_holder_user_id` is set while `IN_USE`.
- **BULK** — a SKU-level quantity of interchangeable stock (cables, mice).
  `asset_tag` is optional. `stock_quantity`/`reserved_quantity` track real
  counts. `status` is restricted to `AVAILABLE`/`RETIRED` only —
  `RESERVED`/`IN_USE`/`IN_REPAIR` describe a single physical unit's state,
  which has no meaning for a SKU-level row. A BULK item never has a
  `current_holder_user_id`.

### 14.3 `inventory_transactions`

**Purpose:** The **permanent, append-only** audit trail for inventory
changes — separate from `ticket_inventory_usage` (§15), which represents
only the *current* ticket↔item relationship. A row here is never updated or
deleted once written (the repository layer overrides `update()`/`delete()`
to raise, and no route exposes either).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | Denormalized from the parent item |
| `inventory_item_id` | `INTEGER` FK → `inventory_items.id` | No | — | |
| `ticket_id` | `INTEGER` FK → `tickets.id`, `ON DELETE SET NULL` | Yes | — | See note below |
| `performed_by_user_id` | `INTEGER` FK → `users.id` | No | — | |
| `transaction_type` | `VARCHAR(20)` (CHECK) | No | — | `CREATED`/`EDITED`/`STOCK_ADJUSTED`/`STATUS_CHANGED`/`HOLDER_CHANGED`/`LOCATION_CHANGED`/`RESERVED`/`RELEASED`/`CONSUMED`/`CONSUME_UNDONE` |
| `quantity_delta` | `INTEGER` | Yes | — | Meaning depends on `transaction_type` |
| `field_name` / `old_value` / `new_value` | `VARCHAR(50)` / `VARCHAR(255)` / `VARCHAR(255)` | Yes | — | Populated for simple field edits (`EDITED`), same pattern as `ticket_history` |
| `notes` | `TEXT` | Yes | — | |
| `created_at` | `DATETIME2(3)` | No | `SYSUTCDATETIME()` | No `updated_at` — append-only |

**Why `ticket_id` uses `ON DELETE SET NULL`, unlike this schema's usual `NO
ACTION` convention:** `TicketService.delete_ticket` hard-deletes ticket rows,
and a `NO ACTION` FK here would make that delete fail the moment a
transaction row references it. `SET NULL` lets the ticket disappear while
the transaction row — and its human-readable ticket reference, preserved
permanently in `notes` — survives, so the item's audit trail is never
truncated just because the ticket that caused an event was later deleted.

**Indexes:** `(company_id, inventory_item_id, created_at)` and
`(company_id, ticket_id)`, both supporting the history views this table
backs.

### 14.4 Design decisions specific to inventory

- Every FK on `inventory_items`/`inventory_transactions` other than the two
  `SET NULL` cases above is `NO ACTION` — company-teardown cascades are
  handled at the application layer, matching this schema's existing
  convention, and SQL Server's "at most one cascade path per table" rule
  would otherwise conflict across the multiple FKs these tables carry.
- `company_id` is denormalized onto every child table (`inventory_items`,
  `inventory_transactions`, `ticket_inventory_usage`) rather than reached
  only via a join through the parent — the same convention `comments`/
  `attachments`/`ticket_history` already use (§7).

---

## 15. Ticket_Inventory_Usage Table

**Table name:** `ticket_inventory_usage`

**Purpose:** The **current** relationship between a ticket and an inventory
item — not a history/audit log (that's `inventory_transactions`, §14.3). A
row exists only while it is true: `RESERVED` (held against the ticket, not
yet used) or `CONSUMED` (actually used to resolve the ticket). Releasing a
reservation or undoing a consumption **deletes the row**.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No (PK) | autoincrement | |
| `company_id` | `INTEGER` FK → `companies.id` | No | — | Denormalized from the parent ticket |
| `ticket_id` | `INTEGER` FK → `tickets.id` | No | — | |
| `inventory_item_id` | `INTEGER` FK → `inventory_items.id` | No | — | |
| `quantity` | `INTEGER` (CHECK > 0) | No | `1` | Always `1` for SERIALIZED |
| `status` | `VARCHAR(20)` (CHECK) | No | — | `RESERVED` \| `CONSUMED` |
| `selected_by_user_id` | `INTEGER` FK → `users.id` | No | — | |

**Unique constraint:** `(ticket_id, inventory_item_id)` — at most one usage
row may exist per ticket+item pair. A second BULK reservation of an
already-attached item merges into the existing row's `quantity` rather than
creating a duplicate row.

### 15.1 Known V1 limitation (intentional, approved, not a bug)

Because at most one row may exist per `(ticket_id, inventory_item_id)`, a
BULK item can only ever be consumed **once** per ticket. Repeated
reservations before consumption keep merging into the same `RESERVED` row,
but once that row is `CONSUMED`, the same item cannot be reserved again on
that ticket until a Company Administrator first undoes the consumption
(the "remove" action) — there is no way to represent a second, independent
consumption of the same item on the same ticket while the first still
stands. A future version could lift this by tracking multiple consumption
events per ticket+item, most naturally by leaning on
`inventory_transactions`' full event history instead of this table's
current-state-only design.

---

## 16. Multi-Tenancy Summary

See `docs/BACKEND_ARCHITECTURE.md` §5–6 for the full design. In short: every
tenant-owned table carries `company_id`, every tenant-scoped repository
extends `CompanyScopedRepository` (which filters every read by `company_id`
and is constructed only with the authenticated caller's own company id —
never a client-supplied value), and the one platform-level user
(`company_id IS NULL`) is served by an entirely separate route group
(`/platform/...`) that never touches tenant data through the normal
company-scoped path.

---

## 17. Complete Mermaid ERD

See `docs/BACKEND_DIAGRAMS.md` §3 for the full, current entity-relationship
diagram covering all 15 tables.

---

## 18. Design Decisions

- **Priority and Category moved from fixed application values to their own
  company-owned tables** (a departure from the original design, which used
  a plain string column for priority) so each company can manage its own
  list without a code change.
- **Ticket `status` still uses controlled, application-level values**
  (`CHECK` constraint, not a lookup table) — the set is small, stable, and
  shared by every company, unlike priority/category.
- **Attachments belong to tickets only, never to comments** — see §12.1.
- **Tickets reference a `locations` row via `location_id`, never free text**
  — a location is chosen from a company-managed list, same pattern as
  category and priority.
- **Files are stored outside SQL Server.** `attachments`/`inventory_items`
  store only metadata and a storage path; content lives on disk.
- **`theme` does not exist anywhere in the final schema.** `companies.theme`
  and `users.theme` were added early, never wired to any real UI behavior,
  and were removed outright in migration `aa1908b341bb` rather than kept as
  dead columns. Do not describe theme as an application feature — see
  `docs/TECH_DEBT.md`.
- **Soft-deactivation (`is_active`), not hard deletion,** for users,
  categories* (*except the one explicit, in-use-checked hard `DELETE`),
  locations, and inventory categories/items — preserving every historical
  reference (tickets, history, transactions) those rows are attributed to.
- **All schema changes go through Alembic**, never manual SSMS edits.

---

## 19. Non-Functional Database Rules

- Foreign keys preserve referential integrity between every related table.
- Unique constraints protect company codes (platform-wide), and
  username/email/title/name per company where uniqueness matters.
- Every timestamp is **UTC**, generated in application code
  (`app.core.time.utc_now_naive`) as the authoritative write path;
  `SYSUTCDATETIME()` database defaults exist only as a defense-in-depth
  fallback for a write path that bypasses the ORM.
- Indexes exist on the columns queried most (e.g.
  `ix_inventory_transactions_company_item_created`,
  `ix_inventory_transactions_company_ticket`), plus every FK and unique
  constraint's implicit index.
- Hard deletion is avoided everywhere history/audit integrity would
  otherwise be lost — the ticket itself is the one entity a Company
  Administrator can still fully delete, and even that cascades its own
  child rows and reverts any inventory it touched rather than leaving
  orphans.
