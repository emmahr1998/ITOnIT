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
