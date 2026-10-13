# ITOnIT — Professor Demo Guide

A connected, ~8–12 minute live walkthrough of the final application through the actual
frontend (web build) — not Swagger. Swagger (`http://127.0.0.1:8000/docs`) is still available
as a fallback or for API-level questions; see `docs/PROFESSOR_QA.md` and
`docs/BACKEND_API_GUIDE.md` for that angle. Every step below uses real, existing
routes/pages/roles and real seeded data — nothing here is aspirational, and every value below
(company code, usernames, ticket number, inventory item) was produced by actually running the
seed scripts and verified live before this guide was written.

**Demo accounts** (seeded by `python -m app.scripts.seed_demo_data`, all on company code
`DEMO001` / **ITOnIT Demo Co** — a dedicated demo company, kept separate from the
`DEFAULT001` company `scripts/create_demo_users.py` seeds):

| Role | Username | Password |
|---|---|---|
| Company Administrator | `admin` | `DemoAdmin123!` |
| Technician | `technician` | `Technician123!` |
| Employee | `employee` | `Employee123!` |
| Employee (2nd) | `employee2` | `Employee2Pass123!` |

The one platform-level **System Administrator** account has no fixed demo password — it comes
from your own `PLATFORM_ADMIN_EMAIL`/`PLATFORM_ADMIN_PASSWORD` in `backend/.env`, created by
running `python -m app.scripts.seed_initial_data` once after setting them. Do this before the
demo and use those credentials at Step 9 — never write the actual password into this file.

---

## Setup (before the audience arrives)

```bash
cd backend
python -m alembic upgrade head
python -m app.scripts.seed_initial_data
python scripts/create_demo_users.py
python -m app.scripts.seed_demo_data
uvicorn app.main:app --reload
```
In a second terminal:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173`. All four commands above are idempotent — safe to re-run this
exact sequence before every rehearsal or the real presentation without creating duplicates.

---

## 1. Public website (~1 min)

Land on `/` — the public marketing page: what ITOnIT is, links to **Sign In** and **Register
Company**. Click **About** to show the About page. Point out: nothing here requires an
account, and no ticket/company data is ever shown pre-login.

## 2. Tenant login (~1 min)

Click **Sign In**. Enter company code `DEMO001`, click through to the username/password
screen — point out the login screen already shows **ITOnIT Demo Co** by name (`POST
/auth/resolve-company` resolved it before any credentials were asked for). Log in as
`employee` / `Employee123!`. Land on the Dashboard — point out it's already populated:
Employee's own tickets, scoped analytics, nothing fabricated. The sidebar shows **Dashboard**,
**My Tickets**, **Create Ticket** only for this role.

## 3. Employee creates a new ticket, live (~1–2 min)

Click **Create Ticket**. Fill in a short realistic example (e.g. title "Mouse stopped
responding", category **Hardware**, priority **Medium**, location **Head Office**). Submit.
Land on the new ticket's detail page — point out the auto-generated `ticket_number`
(`IT-2026-0000NN`, continuing the sequence after the 12 already-seeded tickets) and status
`NEW`. Employee can only edit this ticket while it stays `NEW`, and can only ever see tickets
they created.

## 4. Company Administrator assigns a technician (~1 min)

Log out, log back in as `admin` / `DemoAdmin123!`. Go to **All Tickets** — point out this
account sees all 12+ seeded tickets across every status, not just its own, and that the list's
filters (category/priority/location) are already populated with real company data. Open the
ticket from Step 3, assign it to `technician`. Status auto-advances `NEW → ASSIGNED`.

## 5. Technician handles it: status, comment, attachment (~1–2 min)

Log out, log back in as `technician` / `Technician123!`. Open the ticket just assigned. Change
status to `IN_PROGRESS`. Add a comment describing a quick diagnosis. Optionally upload a small
attachment. Point out: the attachment attaches to the *ticket*, never to a specific comment —
there is no such link in this schema at all (`docs/database-design.md` §12.1 if asked).

## 6. The main story: inventory reserve → consume, live (~2–3 min)

Navigate to ticket **`IT-2026-000012`** — *"Docking station not recognized - external monitor
won't display"* (find it in **Assigned Tickets**, or via the ticket list). This one is already
further along: `IN_PROGRESS`, with two comments already on it (the technician's diagnosis and
the employee's reply) and one attachment (`diagnostic-log.txt`) — narrate that the technician
already diagnosed a faulty docking station and is about to pull a replacement from inventory.

Open its **Inventory** section (still logged in as `technician`) and click **Reserve Item**.
Reserve **Dell WD19 Docking Station** (asset tag `DEMO-DOCK-001`, a SERIALIZED item — point out
the asset tag and the "one physical unit" model). Then click **Consume**. Point out: the item's
status flips to `IN_USE`, its holder becomes the ticket's requester (Priya Employee), and this
also wrote a permanent, append-only `InventoryTransaction` row — visible under **Inventory →
History** for that item, alongside the `CREATED` row from when it was first added to stock.

Change status to `RESOLVED` (as `technician`), then to `CLOSED` (log in as `admin` for this
last step, or skip it if short on time).

## 7. Ticket history — the audit trail (~1 min)

Open `IT-2026-000012`'s **History** tab. Walk through the ordered timeline: created → assigned
→ status changed → two comments → attachment added → inventory reserved → inventory consumed
→ (status changed again if you did Step 6's last transitions). This is the single best screen
to show for "auditing" — every meaningful change, who did it, when, old value → new value.

## 8. Company Administrator: dashboard and admin console (~2 min)

Log back in as `admin`. On the **Dashboard**, point out every number is computed from the real
seeded data: 12+ tickets across all six statuses, a category/priority breakdown, a monthly
trend, and — further down — inventory analytics (7 items, one low-stock `Wireless Mouse`, one
warranty-expiring-soon `Dell WD19 Docking Station`, one in-use serialized laptop). Click a stat
card to show it deep-links into a filtered ticket list. Open **Company Settings** — it only has
Timezone/Language under Preferences (no Theme — removed as an unused, never-wired concept;
worth mentioning if asked). Briefly show **Users** (4 seeded accounts across 3 departments) and
**Inventory** (all 7 items, with **History** available per item and a company-wide transaction
feed for Company Administrator).

## 9. Platform Administrator (~1–2 min)

Navigate to `/platform/login` — a separate login route, no company code field at all. Sign in
with your own configured `PLATFORM_ADMIN_EMAIL`/`PLATFORM_ADMIN_PASSWORD`. Show the **Platform
Overview** — it lists **ITOnIT Demo Co** alongside **Default Company**, both active, with a
combined user count. Open the **Companies** list to show the same. Point out this account has
no visibility into either company's actual tickets/users/inventory — that boundary is enforced
structurally (`docs/BACKEND_ARCHITECTURE.md` §5/§14), not just hidden in the UI.

## 10. Electron desktop app (~1 min)

If a packaged build or `npm run dev`/`npm start` in `desktop/` is already running, front that
window: it opens straight to the company login (not the public site), it's the *same* React
app, and it talks to the same backend over HTTP — Electron bundles neither FastAPI nor SQL
Server. Log into `DEMO001` there too if time allows, to show it's the identical dataset. If
nothing is running, show `desktop/main.js`'s dev/prod origin split and the `app://itonit`
custom protocol instead, and mention the build is unsigned (SmartScreen warning) with no
auto-updater — see the root `README.md`'s desktop section.

---

This closes the loop: the public entry point (1), authentication (2), the full ticket
lifecycle including a live inventory reserve/consume (3–7), company administration (8),
platform administration (9), and the second distribution channel (10) — the same roles and
rules enforced identically everywhere they appear, on a dataset built entirely through the
real application's own services, not hand-inserted rows.
