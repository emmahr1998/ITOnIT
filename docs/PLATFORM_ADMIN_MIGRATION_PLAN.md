# Platform administrator migration & data-repair plan

Status: **proposed — nothing below has been run.** Every step that writes to
SQL Server needs explicit approval first.

Applies to migration `c4e1a7d2b9f0_add_platform_company` (revises
`aa1908b341bb`, the current head on the development database).

## Background

The frontend sent hardcoded role ids (`Employee: 1, Technician: 2,
Company Administrator: 4`). The real `roles` table has different ids:

| id | name |
|----|------|
| 1 | System Administrator |
| 2 | Employee |
| 3 | Technician |
| 4 | Company Administrator |

So choosing **Technician** saved `role_id = 2` (Employee), and choosing
**Employee** saved `role_id = 1` (**System Administrator**). The old
`/platform/*` routes checked only the role name, so any account promoted this
way could use the platform console.

## Current state (read-only audit, 2026-11-01)

From `python -m app.scripts.audit_system_administrators` and direct counts:

| | |
|---|---|
| companies | 2 (`DEFAULT001` id 1, `DEMO001` id 32) |
| users | 10 |
| tickets / ticket_history | 12 / 62 |
| inventory_items / inventory_transactions / ticket_inventory_usage | 8 / 16 / 2 |
| comments / attachments | 7 / 3 |
| departments / categories / locations / priorities | 3 / 5 / 2 / 8 |
| users by (company_id, role_id) | (NULL,1)×1, (1,2)×1, (1,3)×1, (1,4)×2, (32,1)×1, (32,2)×3, (32,4)×1 |

Two accounts hold `System Administrator`:

| id | username | company | created | last updated | verdict |
|----|----------|---------|---------|--------------|---------|
| **93** | `platform-admin` | none (company_id NULL) | 2026-09-28 02:26:38 | never | **Legitimate** |
| 91 | `employee` | DEMO001 (32) | 2026-09-27 22:23:52 | **2026-11-01 12:05:07** | **Accidentally promoted** |

### 1. Which account is legitimate

**User 93 (`platform-admin`).** The evidence:

- It is the only company-less account. That is exactly the row
  `seed_initial_data._seed_platform_administrator` created under the old
  design.
- Its `created_at` matches the platform bootstrap, and it was never modified
  afterwards.
- User 91 is a regular DEMO001 account (username `employee`, created with
  the demo seed). Its role changed at 12:05 today, during a burst of User
  Management edits (users 89, 91, 92, 90, 96 between 12:04 and 12:15).

### What user 91 could have done

There is no platform-action audit log and no request log. Indirect evidence:

- **No platform writes happened.** No company was created, activated or
  deactivated after 12:05. Both companies' `created_at`/`updated_at` date
  from August/September, and there are still only 2 companies.
- 91 has no `ticket_history` or `inventory_transactions` entries today.
- **Read-only platform views cannot be ruled out.** The overview, company
  list and company detail record nothing. If 91 signed in after 12:05, it
  could have seen every company's name, code, status and user/ticket/
  inventory counts. It could not have seen another tenant's tickets, users
  or inventory rows.

### Users 90, 92, 96 — incorrectly saved as Employee?

The old edit modal sent `role_id` on **every** save, even when the role was
untouched. Saving any Employee stored id 1 (System Administrator). Saving any
Technician, or choosing "Technician", stored id 2 (Employee). An account
can therefore only end up at id 2 through the old modal if "Technician" was
selected or it already was a Technician. Read-only evidence:

| id | username | now | evidence | assessment |
|----|----------|-----|----------|------------|
| 90 | `technician` ("Taylor Tech") | Employee, **inactive** (updated 12:10) | Demo Technician. **10 tickets still assigned** to it (55–64, 6 open: ASSIGNED/IN_PROGRESS/WAITING), 15 status changes, 6 inventory reserve/consume/release actions | **Almost certainly a Technician demoted by the bug.** Its open tickets are stranded on a non-Technician. Also confirm whether the deactivation was intended. |
| 96 | `technician2` | Employee | Created today at 12:15 (created = updated). No activity | **Almost certainly meant to be a Technician**: created through the old Create User form with "Technician" selected, which sent id 2. |
| 92 | `employee2` | Employee (updated 12:05:36) | Created 5 tickets, no technician activity | **Ambiguous.** Its history says Employee, but under the old modal it could only land on id 2 if "Technician" was selected at save time. Only you know which was intended. |

None of these are changed automatically. After the new code is live, fix
them through User Management, which now sends the real Technician id (3).
Or, with approval, use a guarded one-row UPDATE per user like step C's.

## Code-level protections already in place (no DB change needed)

These hold as soon as the new backend runs. But the new backend **requires
the migration** (it reads the new columns), so the two go live together.

- Every `/platform/*` route uses `require_system_administrator`. It needs
  the System Administrator role **and** `users.is_system_administrator = 1`
  **and** membership of the `is_platform` company. User 91 fails the last
  two, so it gets 403 even before its role is repaired.
- `POST /platform/login` only matches the flagged platform-company account.
- User management rejects the System Administrator role with an explicit
  400 (`RoleNotAssignableError`). Unknown role ids also get a 400. Nothing
  falls back to Employee.
- JWTs carry only `sub` (user id) and `type`. Role, flag and company are
  re-read from the DB on every request, so a token issued to 91 while it
  was promoted grants nothing extra. No token revocation step is needed.
- The frontend loads role ids from `GET /roles`. No ids are hardcoded.

## Order of operations (why the constraints come after the repair)

```
A. Back up            (no change)
B. Rehearse on a copy (no change to the real DB)
C. Repair user 91     (one UPDATE)          <- must happen BEFORE D
D. alembic upgrade    (columns -> unique indexes -> platform company -> adopt 93)
E. Start new backend + frontend
F. Verify
```

The migration enforces this ordering itself. `_preflight()` runs **before any
DDL** and raises if:

- any user that belongs to a company holds System Administrator (user 91
  today),
- there is more than one company-less user, or the company-less user isn't
  a System Administrator,
- any company already uses `ITONIT-SYSTEM`.

If the preflight raises, nothing is created. SQL Server DDL is
transactional, so the whole revision rolls back regardless. Running step D
before C simply fails with a message naming user 91.

Inside `upgrade()`, the unique indexes are created **before** the only rows
that could violate them are written:

1. add `companies.is_platform` and `users.is_system_administrator` (BIT NOT
   NULL DEFAULT 0, so every existing row gets 0)
2. create `uq_companies_single_platform` (unique, `WHERE is_platform = 1`)
   and `uq_users_single_system_administrator` (unique, `WHERE
   is_system_administrator = 1`)
3. insert the platform company (`is_platform = 1`). The index accepts
   exactly one.
4. update user 93 to point at the platform company with the flag set. The
   index accepts exactly one.

**Code and schema ship together.** The new backend reads the new columns,
so it fails against the old schema. Conversely, the *old* backend's
`seed_initial_data` looks for a company-less System Administrator. After the
migration it finds none and, if `PLATFORM_ADMIN_*` is set, would create a
second, unflagged one. The filtered index can't stop that, because the old
code never sets the flag. Never run the old seed script against the
migrated database.

The seed/bootstrap script (`python -m app.scripts.seed_initial_data`) is
**not needed** for this database: step D adopts user 93. If it is run
afterwards, it reports "already exists, skipped" for both the platform
company and the administrator. It refuses to run, changing nothing, while
any conflicting role holder exists.

## Step A — back up (needs approval to run)

SQL Server Express supports `BACKUP DATABASE` (without compression). Run it
in SSMS or `sqlcmd` against the local instance with Windows authentication.
Replace the path with a folder the SQL Server service account can write to:

```sql
BACKUP DATABASE [<DATABASE_NAME>]
TO DISK = N'C:\SQLBackups\ITOnIT_pre_platform_admin_20261101.bak'
WITH INIT, CHECKSUM, NAME = N'ITOnIT before c4e1a7d2b9f0';

RESTORE VERIFYONLY
FROM DISK = N'C:\SQLBackups\ITOnIT_pre_platform_admin_20261101.bak'
WITH CHECKSUM;
```

Stop the backend first so no writes land between the backup and the
migration.

## Step B — rehearse on a restored copy (recommended)

Restore the backup under another name, point a shell at it, and run the
repair and migration there first. This proves the filtered indexes and the
DML work under the real session settings without touching the real
database.

```sql
RESTORE FILELISTONLY FROM DISK = N'C:\SQLBackups\ITOnIT_pre_platform_admin_20261101.bak';
-- use the logical names it prints:
RESTORE DATABASE [ITOnIT_rehearsal]
FROM DISK = N'C:\SQLBackups\ITOnIT_pre_platform_admin_20261101.bak'
WITH MOVE N'<data_logical_name>' TO N'C:\SQLBackups\ITOnIT_rehearsal.mdf',
     MOVE N'<log_logical_name>'  TO N'C:\SQLBackups\ITOnIT_rehearsal_log.ldf';
```

Then, from `backend/`, with `DATABASE_NAME=ITOnIT_rehearsal` set **only in
that shell's environment** (it overrides `.env`): run step C's SQL against
the rehearsal DB, then `alembic upgrade head`, then step F's checks. Drop
`ITOnIT_rehearsal` afterwards.

## Step C — restore user 91 to Employee (needs approval)

Resolve by role **name**, never by id. Guard on the current state so it is a
no-op if anything has changed since the audit:

```sql
BEGIN TRANSACTION;

UPDATE users
SET role_id    = (SELECT id FROM roles WHERE name = 'Employee'),
    updated_at = SYSUTCDATETIME()
WHERE id = 91
  AND company_id = 32
  AND username = 'employee'
  AND role_id = (SELECT id FROM roles WHERE name = 'System Administrator');

-- expect exactly 1 row affected; otherwise ROLLBACK and re-audit
SELECT u.id, u.username, u.company_id, r.name
FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = 91;

COMMIT;  -- or ROLLBACK
```

This only changes `role_id`/`updated_at` on one row. Its tickets,
comments, attachments and history keep pointing at user 91, and its password
is unchanged.

Before running it, **confirm that Employee is 91's intended role.** The
username suggests it, but only you know what it was before 12:05. Also
decide whether any of users 90, 92 or 96 should be Technician. Those can be
fixed through the new UI after step E.

## Step D — apply the migration (needs approval)

```bash
cd backend
python -m app.scripts.audit_system_administrators   # must show only user 93
alembic upgrade head
```

### 5. What changes and what doesn't

| Table | Change |
|---|---|
| `companies` | +1 column (`is_platform`, 0 for both existing rows), +1 filtered unique index, **+1 row** (`ITOnIT Platform Administration` / `ITONIT-SYSTEM`) |
| `users` | +1 column (`is_system_administrator`, 0 for all rows), +1 filtered unique index; **user 93 only**: `company_id` NULL → platform company id, flag → 1 |
| everything else | **untouched**: tickets, history, comments, attachments, inventory items/transactions/usage, departments, categories, locations, priorities, roles |

No user is created, deleted or re-passworded. Ids, password hashes, and every
foreign key into `users` and `companies` stay as they are.

## Step F — verify (read-only)

### 7. Migration succeeded

```sql
SELECT version_num FROM alembic_version;               -- c4e1a7d2b9f0

SELECT id, name, company_code, is_active, is_platform FROM companies;
-- 3 rows; only ITONIT-SYSTEM has is_platform = 1

SELECT u.id, u.username, u.company_id, u.is_system_administrator, r.name
FROM users u JOIN roles r ON r.id = u.role_id
WHERE r.name = 'System Administrator' OR u.is_system_administrator = 1;
-- exactly one row: 93, platform company id, 1, System Administrator

SELECT COUNT(*) FROM users WHERE company_id IS NULL;   -- 0

SELECT name, is_unique, has_filter, filter_definition
FROM sys.indexes
WHERE name IN ('uq_companies_single_platform', 'uq_users_single_system_administrator');
-- 2 rows, is_unique = 1, has_filter = 1
```

Then re-run the counts in the table at the top. Everything must match, except
`companies` = 3 and the users-by-(company, role) breakdown, where (NULL,1)
becomes (platform id,1) and (32,1) becomes (32,2).

**Constraint-violation checks run ONLY against the restored
`ITOnIT_rehearsal` database (step B), never the real one.** Confirm the
session is on the rehearsal DB first (`SELECT DB_NAME();`), then expect
error 2601 from each statement:

```sql
-- REHEARSAL DATABASE ONLY
BEGIN TRANSACTION;
UPDATE users SET is_system_administrator = 1 WHERE id = 91;           -- 2601
INSERT INTO companies (name, company_code, is_active, is_platform, timezone, language)
VALUES ('Dup', 'DUP-PLATFORM', 1, 1, 'UTC', 'en');                     -- 2601
ROLLBACK;
```

On the real database, step F stays read-only. The `sys.indexes` query above
is enough to show the constraints exist.

`python -m app.scripts.audit_system_administrators` should list exactly one
holder.

### 9. Technician persistence (UI, as a DEMO001 Company Administrator)

1. User Management → edit an Employee → Role: Technician → Save. The table
   shows Technician.
2. Hard-refresh the page. It still shows Technician.
3. Sign that user in (DEMO001 code). They get the Technician dashboard,
   Assigned Tickets, and Inventory in the sidebar, and no User Management.
4. Change them back to Employee. It persists, and their next login shows the
   Employee dashboard.
5. The role dropdown never offers System Administrator. In DevTools →
   Network, `GET /roles` returns the three company roles with ids
   2/3/4, and the PATCH body's `role_id` matches.

### 10. Global System Administrator access

1. `/platform/login` with the `platform-admin` account. The dashboard
   loads.
2. Companies lists DEFAULT001 and DEMO001 only. ITONIT-SYSTEM never appears,
   and the overview's totals exclude it.
3. Open a company's details. Deactivate it, confirm its users are refused,
   then reactivate it.
4. `/login` with company code `ITONIT-SYSTEM` reports an unknown company.
   The platform account can't open the tenant app.
5. Sign in as user 91 (DEMO001). It gets the Employee dashboard, and
   visiting `/platform` sends it back to `/dashboard`. Its old tokens
   can't reach `/platform/*`.
6. `/platform/login` with user 91's credentials returns 401.

## 8. Rollback

From least to most drastic:

1. **Preflight or migration fails partway.** Nothing to do: the revision is
   one transaction and SQL Server rolls it back. `alembic_version` stays at
   `aa1908b341bb`.
2. **Migration succeeded but the app misbehaves.** Stop the new backend,
   then run `alembic downgrade aa1908b341bb`. This moves user 93 back to
   company_id NULL, deletes the platform company, and drops both indexes
   and columns. Then run the previous backend/frontend build. Note that the
   **old frontend still has the hardcoded-id bug**, so don't edit roles
   while rolled back.
3. **Anything unexpected with data.** Stop the backend and restore the
   step-A backup:

   ```sql
   USE master;
   ALTER DATABASE [<DATABASE_NAME>] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
   RESTORE DATABASE [<DATABASE_NAME>]
   FROM DISK = N'C:\SQLBackups\ITOnIT_pre_platform_admin_20261101.bak'
   WITH REPLACE, CHECKSUM;
   ALTER DATABASE [<DATABASE_NAME>] SET MULTI_USER;
   ```

   This also undoes step C, so user 91 is a System Administrator again.
   Keep the old backend offline until the repair is redone.

## Approvals needed

1. Step A: take the backup (and B: restore a rehearsal copy).
2. Confirm user 91's intended role (Employee?), and decide about users 90,
   92 and 96.
3. Step C: run the one-row UPDATE on the real database.
4. Step D: `alembic upgrade head` on the real database.
5. (Optional) run `seed_initial_data` afterwards. It should be a no-op.
6. Commit / push of the code changes.
