# Technical Debt & Deferred Issues

Known gaps identified during development that are intentionally deferred to
a specific later milestone rather than fixed opportunistically. Each entry
records what's wrong, why it wasn't fixed when found, and which milestone
owns the fix — so it isn't forgotten and isn't fixed twice.

## Multi-tenant migration (see the Company/SaaS architecture plan)

### 1. ✅ RESOLVED — `POST /auth/register` created accounts with `company_id = None`

**Found:** during the Milestone 2 tenant-isolation audit (2026-08-06).

**Resolved:** 2026-08-08, as part of Milestone 5 (Company registration +
default data seeding). No longer an open item - kept below for the
historical record of what was wrong and why.

**What's wrong:** `AuthService.register` (`backend/app/services/auth_service.py`)
predates the multi-tenant plan and never sets `company_id` on the `User` it
creates. Since `User.company_id` is nullable, this doesn't raise a database
error — it silently creates a company-less account. Verified empirically:
the account gets valid tokens and `GET /auth/me` works, but every
company-scoped endpoint (e.g. `GET /departments`) returns
`403 "This account has no associated company"` via
`get_current_company_id` — the account is a functional dead end.

**Why deferred:** Milestone 2's scope was enforcing scoping in existing
repositories/services, not building company selection into registration.
Milestone 2's instructions explicitly excluded changing the auth flow
unless strictly required for isolation — this endpoint doesn't leak
cross-company data, it just produces an unusable account, so it wasn't
in scope.

**Not a tenant-isolation violation** — no cross-company data exposure.
It's an account-usability gap.

**Worsened by Milestone 4 (2026-08-06):** now that `POST /auth/login`
requires a `company_code`, a self-registered `company_id = None` account
can't log in *at all* through the normal flow anymore (previously it could
log in and only 403'd on company-scoped routes afterward). Still not a
tenant-isolation issue - just a harder dead end than before. Not fixed now,
for the same reason as before: the real fix is company-code-first
registration, which is Milestone 5's job.

**Fix applied:** `POST /auth/register` and `AuthService.register` were
removed outright (not left as a redirect or deprecated alias) - replaced by
`POST /companies/register` / `CompanyService.register_company`, which
creates the company, its first Company Administrator, and starter company
data (priorities, categories, a location, a department) all in one
transaction, then signs the new admin in immediately. Employees and
Technicians can no longer self-register at all - only a Company
Administrator can create them afterward, via the existing `POST /users`.

**Verified:** `POST /auth/register` now returns 404 (see
test_auth.py::test_old_self_registration_endpoint_no_longer_exists);
`tests/test_company_registration.py` covers the new endpoint end-to-end,
including that a client-supplied `role_id`/`company_id` in the request
body has no effect (the schema has no such fields at all - Pydantic
silently drops unknown fields), and that two independently registered
companies' seeded data and users stay isolated from each other.

**One planned piece deferred further, not built here:** the architecture
plan's Milestone 5 section also lists seeding starter Inventory Categories
per company. The `inventory_categories` table doesn't exist yet - it's
Milestone 10's job (Inventory core) - so building it now would mean
throwaway inventory models ahead of schedule. `CompanyService._seed_defaults`
has a comment marking exactly where that seeding call belongs once
Milestone 10 lands.

**Update, 2026-08-10 (Milestone 10, Phase 10.1):** resolved. `inventory_categories`
now exists; `CompanyService._seed_defaults` seeds the eleven starter names
for every newly registered company, and a dedicated, idempotent data
migration (`backfill inventory categories for existing companies`) seeds the
same list for every company that registered before this phase existed.
Verified against the real dev database (existing `DEFAULT001` company
backfilled to exactly 11 rows, re-running the backfill logic a second time
adds none) and against a completely fresh, from-scratch database (same
11-row result after running the full migration chain to head) - see Phase
10.1's verification report for the complete results.

### 2. ✅ RESOLVED — `app/scripts/seed_initial_data.py` and `scripts/create_demo_users.py` were stale under the multi-tenant model

**Found:** during the Milestone 2 tenant-isolation audit (2026-08-06).

**Resolved:** 2026-08-06, as part of Milestone 3's fresh-database bootstrap
fix. No longer an open item - kept below for the historical record of what
was wrong and why, plus how it was verified fixed.

**What was wrong:** Both are dev-only CLI scripts, not reachable from any
API route.
- `app/scripts/seed_initial_data.py` called `PriorityRepository(db)` with no
  `company_id` — `PriorityRepository.__init__` requires it, so this raised
  `TypeError` immediately.
  **Verified empirically to be worse than it first looked (2026-08-06,
  Milestone 3 fresh-database check):** `main()` wrapped `_seed_roles`,
  `_seed_priorities`, and `_seed_admin_user` in one try/except that called
  `db.rollback()` on any exception before a single `db.commit()` at the
  end. Since `_seed_priorities` crashed before that commit, the crash
  **also rolled back the otherwise-successful role inserts from
  `_seed_roles`** - on a genuinely fresh database, running the documented
  setup (`alembic upgrade head` then `python -m app.scripts.seed_initial_data`)
  left the `roles` table with only `System Administrator`, not the four
  intended roles. Every database that had ever been bootstrapped before
  Milestone 2 was unaffected, since its roles were seeded back when this
  script still worked - only a brand-new setup hit this.
- `scripts/create_demo_users.py` called `UserRepository(db)` (harmless -
  `UserRepository` allows unscoped construction) but constructed each
  `User(...)` with no `company_id`, which didn't error (the column is
  nullable) but produced the same orphaned, company-less account described
  in item 1.

**Fix applied:** `seed_initial_data.py` now resolves the Default Company
seeded by the `add_companies_table` migration by its `company_code`
(`DEFAULT001`) rather than assuming a hardcoded id, and threads that
`company_id` through `PriorityRepository` and every seeded `Priority`/
`User` - removing the root cause of the crash rather than restructuring
around it. The bootstrap stays a single atomic transaction (one commit,
one rollback) as it was before - "commit each step separately" was
explicitly rejected as a fix, since a partially-seeded database is worse
than an unseeded one. `create_demo_users.py` now resolves the same Default
Company and constructs a company-scoped `UserRepository`, so it can no
longer produce an orphaned `company_id = None` user.

**Verified** against a genuinely fresh, from-scratch throwaway database
(created and dropped for this check, dev database untouched): the full
migration chain plus `python -m app.scripts.seed_initial_data` produces
exactly the four roles (Employee, Technician, Company Administrator,
System Administrator), the Default Company, all four priorities scoped to
it, and the optional admin user scoped to it. Running the seed script (and
`create_demo_users.py`) a second time is fully idempotent - no duplicate
rows, no overwritten password hashes.

### 3. `docs/BACKEND_ARCHITECTURE.md`, `BACKEND_API_GUIDE.md`, `BACKEND_SUMMARY.md`, `BACKEND_DIAGRAMS.md`, `database-design.md`, `PROFESSOR_DEMO_GUIDE.md`, `PROFESSOR_QA.md` predate the entire multi-tenant migration

**Found:** during Milestone 3 (role consolidation), while updating role
terminology (2026-08-06).

**What's wrong:** none of these seven files mention "Company" anywhere
(verified with a direct grep) - they document the system exactly as it was
before Milestone 1 introduced the `Company` entity at all. This is broader
than role naming: they don't describe tenant scoping, the `company_id`
column, `CompanyScopedRepository`, or any of Milestones 1-3's actual
behavior. A surface-level "Administrator" → "Company Administrator"
find-replace across these files was deliberately **not** done, because it
would make them look current while the underlying architecture description
stays entirely wrong - worse than leaving them clearly out of date.

**Why deferred:** rewriting these accurately requires documenting the whole
multi-tenant architecture (companies, scoping, the eventual role/auth/
inventory/platform surface), which is explicitly **Milestone 14**'s
job per the architecture plan ("README/architecture docs rewritten for the
SaaS model") - doing it piecemeal now, one migration ahead of schedule and
before Milestones 4-13 even exist, would mean rewriting the same sections
repeatedly as each later milestone lands.

**Resolution:** comprehensive rewrite during **Milestone 14 — Cleanup &
docs**, once the full SaaS architecture (auth, roles, inventory, platform
console, Electron) actually exists to document. `README.md` is the one
exception - its "Default accounts" table and role descriptions were kept
current in Milestone 3 since they're short, concrete, and directly tied to
`scripts/create_demo_users.py`, not a narrative architecture description.

### 4. ✅ RESOLVED — Frontend role-keyed lookups still used the pre-Milestone-3 role names — crashed the authenticated app shell for every real user

**Found:** during Milestone 4's live-browser verification of the new
login flow (2026-08-06) - the first time any milestone actually completed
a full login round-trip in a browser since Milestone 3 changed the role
names on the backend.

**Resolved:** 2026-08-08, as a dedicated frontend compatibility pass
before committing Milestone 4 (the crash made the authenticated app
unusable, so the user asked to close this out immediately rather than
defer it further). No longer an open item - kept below for the historical
record of what was wrong, plus what changed to fix it.

**What's wrong:** `frontend/src/types/auth.ts`'s `Role` type is still
`"Employee" | "Technician" | "Manager" | "Administrator"` - never updated
for Milestone 3's role consolidation (deferred there on purpose; see the
approved Milestone 3 plan's "Frontend Impact" section, never implemented).
`frontend/src/components/layout/Sidebar.tsx` declares
`NAV_BY_ROLE: Record<Role, NavSection[]>`, keyed by those same four
strings. A real user's `role` from `GET /auth/me` is now `"Company
Administrator"` or `"System Administrator"` - neither is a key in
`NAV_BY_ROLE`, so `NAV_BY_ROLE[user.role]` is `undefined`, and the
component crashes rendering it (`TypeError: Cannot read properties of
undefined (reading 'map')`). Verified live: logging in as the demo admin
(`admin` / `Admin123!` / company code `DEFAULT001`) succeeds completely
(`POST /auth/login` → 200, `GET /auth/me` → 200, redirect to `/dashboard`
fires) - the crash happens in the authenticated app shell immediately
after, not in anything Milestone 4 built. The same class of bug likely
exists in `TicketListPage.tsx`'s `PAGE_TITLE_BY_ROLE`/`EMPTY_STATE_BY_ROLE`
and `DashboardPage.tsx`'s `role === "Administrator"` string comparisons
(the plain-comparison ones fail silently instead of crashing, but are
equally wrong now).

**Why deferred:** this is exactly the frontend work the Milestone 3 plan
explicitly scoped out ("Frontend Impact — do not implement yet"), approved
as deferred at the time. Milestone 4's job was the login flow itself, not
a general frontend role-string sweep - fixing `Sidebar.tsx` alone wouldn't
close this out, since the other files listed in Milestone 3's Frontend
Impact section (`TicketListPage.tsx`, `DashboardPage.tsx`,
`CreateUserModal.tsx`, `AppRouter.tsx`, `types/user.ts`'s hardcoded
`ROLE_IDS`) have the identical problem and belong to the same pass.

**Impact:** every real login (any role except a bare Employee whose nav
happens not to crash - unverified either way) currently lands on a broken,
crashing authenticated app - not a login-flow defect, but a real blocker
for actually using the app today.

**Fix applied:** `types/auth.ts`'s `Role` type is now `"Employee" |
"Technician" | "Company Administrator" | "System Administrator"`. Every
role-keyed lookup was updated to match: `Sidebar.tsx`'s `NAV_BY_ROLE`
(Manager and Administrator's nav sections merged into one "Company
Administrator" entry - the superset, Main + Management - with a new,
deliberately-empty "System Administrator" entry, since no real UI exists
for that role yet); `TicketListPage.tsx`'s `HEADING_BY_ROLE`/
`EMPTY_STATE_BY_ROLE` and its inline create-ticket-button check;
`DashboardPage.tsx`'s separate `isManager`/`isAdmin` booleans collapsed
into one `isCompanyAdmin` (Manager and Administrator became the same role,
so their dashboard sections are now the same code path - the
previously-Administrator-only KPI card set, quick actions, and widgets);
`AppRouter.tsx`'s `ADMIN_ROLES`/`CREATE_TICKET_ROLES`; `TicketSidebar.tsx`'s
`canManage`; `CreateUserModal.tsx`, `UserEditModal.tsx`, and `UsersPage.tsx`'s
role dropdown/filter. `types/user.ts`'s `ROLE_ID_BY_NAME`/`ROLE_OPTIONS` are
now typed as `Record<AssignableRole, number>`/`AssignableRole[]` (a new
`Exclude<Role, "System Administrator">` type) rather than `Record<Role, ...>`,
since a company-scoped admin UI has no business offering the platform-only
System Administrator role as something to assign, and that role's id isn't
even reliably knowable from the frontend (confirmed empirically: it varies
by install history). TypeScript's exhaustiveness checking on the `Record<Role,
...>` types was used as the systematic checklist for this pass - fixing the
`Role` type first and re-running `tsc -b` surfaced every remaining file
needing an update as a compile error, including two (`UserEditModal.tsx`,
`UsersPage.tsx`) not found by the earlier manual audit.

**Verified:** `tsc -b`, `oxlint`, and `vite build` all clean. Live browser
verification: logged in as Employee, Technician, and Company Administrator
(the demo admin, formerly "Administrator") - each reaches `/dashboard`
without a console error, the sidebar renders the correct nav for its role,
and role-gated widgets/actions show correctly. No frontend route or UI
exists yet for System Administrator to log into (that's Milestone 8), so
it wasn't exercised end-to-end, but the nav/role-keyed lookups no longer
crash for it either.

## Inventory & Ticket integration (Milestones 11-12)

### 1. Ticket deletion and its inventory cleanup are two separate commits, not one atomic transaction

**Found:** during Milestone 11 (Ticket ↔ Inventory integration); reconfirmed
during Phase 12.1's final audit (2026-08-12) once `InventoryTransaction`
rows started riding along on the same commit.

**What's wrong:** `TicketService.delete_ticket` calls
`TicketInventoryService.release_all_for_ticket` *before* deleting the
ticket row. `release_all_for_ticket` reverts every attached inventory
item's RESERVED/CONSUMED state (and, as of Phase 12.1, writes the
corresponding `InventoryTransaction` audit rows) and commits that as its
own transaction; `delete_ticket` then deletes the ticket row and commits
separately, afterward. These are two independent commits, not one atomic
unit of work.

**Practical consequence:** if the *second* commit (the ticket-row delete)
were to fail for any reason, the inventory cleanup - including
`InventoryTransaction` rows whose `notes` say "Ticket IT-... deleted;
... reverted automatically" - would already be durably committed, even
though the ticket itself was never actually deleted. The inventory side
would be left correctly reverted (no stuck RESERVED/IN_USE item), but the
audit trail would reference a deletion that didn't happen.

**Why deferred:** this is pre-existing Milestone 11 behavior, deliberately
accepted at the time (see Milestone 11's own completion report) rather
than something Phase 12.1 introduced. It is not blocking either
milestone's implementation - the far more common failure mode (the first
commit failing) already leaves everything correctly rolled back, and nothing
in Milestones 11 or 12's approved scope required stronger cross-resource
atomicity than this.

**Future improvement (not implemented, not scheduled to a milestone yet):**
make ticket deletion and its inventory cleanup one atomic transaction -
e.g. by having `TicketService.delete_ticket` pass its own session/deferred
commit into `release_all_for_ticket` (or restructuring so both operations
share a single `commit()` at the very end of `delete_ticket`) rather than
`release_all_for_ticket` committing independently.

### 2. SQL Server text columns are non-Unicode (`varchar`/`text`) - non-ASCII characters silently corrupt to `?`

**Found:** during live verification of the Inventory Transaction History
frontend (2026-08-20), while checking that `TicketInventoryService.consume`'s
auto-generated note for a SERIALIZED item -
`f"Status RESERVED→IN_USE; holder assigned to {...}"` - rendered correctly
in the new History modal.

**What's wrong:** the note displayed as `Status RESERVED?IN_USE; ...` - the
`→` (U+2192) had become a literal `?`. Traced end to end, not a display
bug: the source file itself is correctly UTF-8 on disk (confirmed via raw
byte inspection - `\xe2\x86\x92` at that location), and querying the
resulting row directly from the database via SQLAlchemy (bypassing the API
entirely) shows the stored value already contains `?`, not `→` - the
corruption happens on write to SQL Server, not in transit or in the
frontend. Root cause: `notes` (and `field_name`, `old_value`, `new_value`,
`transaction_type`) on `inventory_transactions` are all SQL Server
`varchar` (confirmed via `INFORMATION_SCHEMA.COLUMNS`), not `nvarchar` -
SQLAlchemy's generic `sa.String()`/`sa.Text()` map to the mssql dialect's
non-Unicode types by default. A schema-wide check
(`INFORMATION_SCHEMA.COLUMNS WHERE DATA_TYPE IN ('varchar','text')`)
returns **53 columns across the entire database** - `comments.content`,
`attachments.original_filename`, `companies.name`, and effectively every
user-visible text column in the schema, not something specific to
`inventory_transactions` or this milestone. Any of those columns has
always been able to silently replace a non-ASCII character (accented
letters, curly quotes, em dashes, emoji, non-Latin scripts, and this
arrow) with `?` on write.

**Why deferred:** this is a pre-existing, schema-wide condition that
happened to surface via one transaction's generated note during this
milestone's manual testing - it predates Phase 12.1 and the History
frontend entirely and isn't caused by either. Fixing it properly means
auditing all 53 columns, deciding which are genuinely user-visible/
non-ASCII-relevant versus system-internal (e.g. `alembic_version.version_num`
doesn't need it), and a dedicated Alembic migration to `ALTER COLUMN` the
relevant ones from `varchar`/`text` to `nvarchar`/`nvarchar(max)` - a
cross-cutting schema change well outside this milestone's explicit
"frontend only, no backend/schema changes" scope. Not fixed here per
direct instruction.

**Not recoverable for existing data:** any row that already had a
non-ASCII character written to one of these columns has had that
character permanently replaced with `?` - the original byte is gone from
the database, not just hidden. A future fix stops new corruption; it
cannot restore what a `varchar` column already overwrote.

**Future improvement (not implemented, not scheduled to a milestone yet):**
a dedicated migration/audit pass - not bundled into any other feature -
that (1) enumerates every `varchar`/`text` column via
`INFORMATION_SCHEMA.COLUMNS`, (2) evaluates each for whether it should be
Unicode-capable (`NVARCHAR`/`NVARCHAR(MAX)`) given what it stores, (3)
updates the corresponding SQLAlchemy column types so future migrations
default to Unicode-safe types on this dialect, and (4) documents, for
anyone debugging historical data, that a `?` where a special character
would be expected may indicate this bug rather than genuine user input.

## Analytics & Dashboard prerequisite: UTC timestamp normalization

### ✅ RESOLVED (code) / ⏳ PENDING (data) — every system timestamp column was silently DB-server-local time, not UTC

**Found:** during design review for the Analytics & Dashboard milestone
(2026-08-22), while working out how `Company.timezone` should back
"Created Today"/"Resolved Today" boundaries.

**What was wrong:** `CreatedAtMixin`/`TimestampMixin` (`app/models/mixins.py`)
populated `created_at`/`updated_at` via SQL Server's `CURRENT_TIMESTAMP`
(`server_default=func.now()`), which reflects the **database server's own
OS clock** - confirmed empirically against the real dev SQL Server
(`GETDATE()` read `17:35:12` local while `GETUTCDATE()` read `14:35:12`
UTC, a +03:00 offset with no relationship to any company's configured
timezone). Meanwhile `Ticket.resolved_at`/`closed_at` and
`Comment.updated_at` were set explicitly in application code via
`datetime.now(timezone.utc)` - genuinely UTC. These two families of
timestamps were never on the same basis: `resolved_at - created_at`
(average resolution time; also `frontend/src/utils/ticketAge.ts`'s
`ticketAgeDays()`) was silently wrong by the DB server's UTC offset for
every ticket that has ever been resolved, in every environment, since the
very first migration - not something the Analytics phase introduced,
just the first place it would have produced a visibly wrong number.

Separately, confirmed Pydantic serializes a naive `datetime` with no
`Z`/offset suffix; the frontend's `new Date(...)` calls (12+ files) then
parse an unmarked ISO string as the **browser's local time** per the
ECMAScript spec - a second, independent ambiguity on top of the write-side
one.

**Root-cause fix applied:** `app/core/time.py` adds one function,
`utc_now_naive()` (`datetime.now(timezone.utc).replace(tzinfo=None)`),
now the sole generator of every persisted system timestamp in this schema:
`CreatedAtMixin.default`/`TimestampMixin.default`/`.onupdate`,
`TicketService.change_status`'s `resolved_at`/`closed_at`, and
`CommentService.update_comment`'s `updated_at`. Persisted values are
**naive UTC, not aware UTC** - empirically proven byte-identical for
storage purposes (SQL Server's `DATETIME`/`DATETIME2` types cannot carry
timezone information at all; an aware value round-trips through pyodbc
indistinguishable from a naive one, confirmed against the real dev SQL
Server with a throwaway table, since dropped) - naive was chosen anyway
to avoid a subtler footgun: mixing an aware in-memory object with a
naive one fetched via a separate query risks a timing-dependent
`TypeError: can't subtract offset-naive and offset-aware datetimes`.

Migration `73bda2fc3df1` changes all 25 audited system timestamp columns
from `DATETIME` to `DATETIME2(3)` (lossless; also removes an implicit
precision-truncating cast that occurred every time `SYSUTCDATETIME()`,
which returns `datetime2(7)`, fed a plain `DATETIME` column's default) and
replaces the `CURRENT_TIMESTAMP` default constraint with `SYSUTCDATETIME()`
on exactly the 22 columns that had one (the other 3 -
`tickets.resolved_at`, `tickets.closed_at`, `comments.updated_at` - are
transition-specific, application-set-only fields with no default before
or after). The DB-level default is a defense-in-depth fallback only; the
Python-side default is authoritative for every write, since 100% of
writes in this codebase go through the ORM. The one index referencing an
audited column (`ix_inventory_transactions_company_item_created`) is
dropped and recreated around the type change; confirmed via
`sys.indexes`/`sys.index_columns` against the real dev DB that no other
index touches any of the 25 columns.

New `app/schemas/types.py`'s `UTCDatetime` (a Pydantic `Annotated` type)
attaches UTC tzinfo to a naive value at the API boundary, applied to every
system-timestamp field across all 12 response schemas that had one - so
JSON responses carry an explicit `Z`/`+00:00` suffix and the frontend's
existing `new Date(...)` calls parse correctly, with **no frontend code
changes**.

**⏳ Not yet done - deliberately, pending separate explicit approval:**
this migration does not touch any existing row's timestamp *values* - only
column type and default constraints. Historical rows written before this
migration keep whatever digits they already had, and **that basis cannot
be reliably recovered**: comparing a row's timestamp against any recorded
cutover marker is ambiguous within a window as wide as the DB server's
UTC offset (a row written moments after cutover has smaller UTC-basis
digits than a local-basis cutover marker would suggest, and gets
misclassified - confirmed by construction, not assumption). The only
ambiguity-free discriminator is primary key `id` (monotonic, unaffected by
clock basis), which would work but adds permanent per-table cutover-id
bookkeeping to the serialization layer for the sake of a genuinely tiny
amount of dev-only data (measured on the real dev DB at design time: 1
company, 10 users, 3 tickets, 1 comment, 1 attachment, 8 history rows,
11 inventory categories, zero inventory items/usage/transactions).

**Chosen resolution:** reseed the dev database from scratch after this
migration lands, rather than build and maintain that bookkeeping. Until
that reseed happens, existing rows' timestamps remain of **unproven
basis** - do not treat a `?`-column-bug-style assumption ("it's probably
fine") as fact, and do not build any feature that computes exact
durations or day-boundaries from data older than the reseed without
accounting for this. The reseed itself is a separate, explicitly-gated,
destructive step - not part of this fix - see the Analytics & Dashboard
Phase A follow-up report for the exact proposed reset/reseed commands,
pending approval.

**Follow-up correction (same day):** reseeding alone was found insufficient
- even a completely *fresh* database still receives ~16 rows on the wrong
time basis, because three older, already-applied migrations
(`e05a93267ebf`, `b8c5e972dfbf`, `5aeede95b6be`) seed static metadata (the
Default Company row, its 4 starter priorities, its 11 starter inventory
categories) via raw `CURRENT_TIMESTAMP` SQL that runs *before* this
migration in the chain. Rather than edit those historical migration files,
migration `73bda2fc3df1` gained one additional, narrowly-targeted step
(`_normalize_seed_metadata_timestamps`, run last, only in `upgrade()`) that
rewrites exactly those rows' `created_at`/`updated_at` to `SYSUTCDATETIME()`
- matched by stable business identifiers only (`company_code`, priority
`title`, category `name`, always scoped through the Default Company's own
id), never a hardcoded numeric id, and never touching a same-named
priority/category belonging to a different, real company. These rows are
static system/default metadata, not user-generated history, so overwriting
their original (already-wrong) creation instant loses no meaningful audit
value - unlike every ticket/comment/attachment/inventory-transaction/
ticket-history row, which this step never touches and which remain exactly
as ambiguous as described above until the reseed. `downgrade()`
deliberately does not attempt to revert this specific step - there is no
correct value to revert *to*.

**Verified:** throwaway-database migration run (`alembic upgrade head`
against a fresh DB), ORM write/round-trip checks, raw-SQL
`SYSUTCDATETIME()` fallback check, live HTTP API serialization check, and
a real create→resolve→measure arithmetic check all passing with no
~3-hour skew - full results in the Analytics & Dashboard Phase A report(s).
Re-verified after the follow-up correction: Default Company, all 4
priorities, and all 11 inventory categories now read UTC-basis
`created_at`/`updated_at` on a completely fresh database - zero known
DB-local-basis timestamps remain anywhere in a fresh install. Real dev
database **not** touched by any of this verification.
