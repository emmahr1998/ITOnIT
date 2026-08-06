# Technical Debt & Deferred Issues

Known gaps identified during development that are intentionally deferred to
a specific later milestone rather than fixed opportunistically. Each entry
records what's wrong, why it wasn't fixed when found, and which milestone
owns the fix — so it isn't forgotten and isn't fixed twice.

## Multi-tenant migration (see the Company/SaaS architecture plan)

### 1. `POST /auth/register` creates accounts with `company_id = None`

**Found:** during the Milestone 2 tenant-isolation audit (2026-08-06).

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

**Resolution:** remove or replace `POST /auth/register` with the
company-code-first registration flow (`POST /companies/register`) during
**Milestone 5 — Company registration + default data seeding**, which
creates the company, the first Company Administrator, and seeds default
data all in one transaction.

### 2. `app/scripts/seed_initial_data.py` and `scripts/create_demo_users.py` are stale under the multi-tenant model

**Found:** during the Milestone 2 tenant-isolation audit (2026-08-06).

**What's wrong:** Both are dev-only CLI scripts, not reachable from any API
route.
- `app/scripts/seed_initial_data.py` calls `PriorityRepository(db)` with no
  `company_id` — `PriorityRepository.__init__` now requires it, so this
  raises `TypeError` immediately (and even if it didn't,
  `Priority(title=title)` has no `company_id`, which is `NOT NULL` on that
  table since Migration 1).
- `scripts/create_demo_users.py` calls `UserRepository(db)` (fine —
  `UserRepository` still allows unscoped construction) but constructs each
  `User(...)` with no `company_id`, which doesn't error (the column is
  nullable) but produces the same orphaned, company-less account described
  in item 1.

**Why deferred:** neither script is part of the deployable application or
reachable through any endpoint, so neither affects tenant isolation or any
customer-facing behavior. Fixing them productively requires deciding what
"seed data for a multi-tenant install" even means (per-company seeding is
Milestone 5's job), so a real fix belongs with that design, not as a
one-off patch now.

**Resolution:** update or retire both scripts during
**Milestone 14 — Cleanup & docs**, once Milestone 5's per-company default
data seeding exists and it's clear whether these standalone scripts still
serve a purpose (e.g. a `--company-id` flag for local dev) or should be
deleted in favor of the real registration flow.
