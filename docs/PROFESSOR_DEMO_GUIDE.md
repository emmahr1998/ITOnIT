# ITOnIT — Professor Demo Guide

A step-by-step script for demonstrating the backend live, entirely through Swagger — no
frontend needed. Budget ~15–20 minutes for the full walkthrough. Every step below has been
run against the real project exactly as written.

Demo accounts (seeded by `scripts/create_demo_users.py` — see Step 2):

| Role | Username | Password |
|---|---|---|
| Employee | `employee` | `Employee123!` |
| Technician | `technician` | `Technician123!` |
| Manager | `manager` | `Manager123!` |
| Administrator | `admin` | `Admin123!` |

> **Known quirk, worth knowing before you're live:** if your local dev database was seeded
> earlier via `app.scripts.seed_initial_data` with an `INITIAL_ADMIN_EMAIL`/
> `INITIAL_ADMIN_PASSWORD` set in `.env`, the `admin` account may already exist with **that**
> password instead of `Admin123!` (the demo script never overwrites an existing account,
> matched by username or email). If `admin` / `Admin123!` fails to log in, check
> `INITIAL_ADMIN_PASSWORD` in your `.env` file and use that instead — it is not a bug, just
> two different scripts both being allowed to create the same account.

---

## 1. Start the backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

You should see Uvicorn report it's running on `http://127.0.0.1:8000`. Leave this terminal
open and running for the rest of the demo.

## 2. Run migrations and seed data

In a second terminal, also from `backend/`:

```bash
python -m alembic upgrade head
python -m app.scripts.seed_initial_data
python scripts/create_demo_users.py
```

- The first command applies every migration up to the latest schema.
- The second seeds the four roles (Employee/Technician/Manager/Administrator) and the four
  default priorities (Low/Medium/High/Critical) — safe to re-run, it skips anything that
  already exists.
- The third creates the four demo accounts in the table above — also safe to re-run.

(If this is a completely fresh database, also run `POST /categories` and `POST /locations`
once each with a couple of sample values before Step 5, since a fresh install has none yet —
see Step 11.)

## 3. Open Swagger

Navigate to **`http://127.0.0.1:8000/docs`** in a browser. This is FastAPI's auto-generated,
interactive API documentation — every endpoint, request shape, and response shape you see is
generated directly from the running code, not hand-written.

Point out: the padlock icon next to protected endpoints, and the **Authorize** button at the
top right — that's what Step 4 uses.

## 4. Log in

1. Expand **`POST /auth/login`**, click **Try it out**.
2. Request body:
   ```json
   {"username": "manager", "password": "Manager123!"}
   ```
3. Click **Execute**. The response body contains `access`, `refresh`, and `token_type`.
4. Copy the `access` token value (without quotes).
5. Click **Authorize** at the top of the page, paste the token into the value field, click
   **Authorize**, then **Close**.

Every subsequent "Try it out" call in this Swagger session now sends
`Authorization: Bearer <token>` automatically. We're logged in as **Manager** for the next
few steps.

Optional talking point: expand **`GET /auth/me`** and execute it with no body — it returns
the current user's profile and role, proving the token round-trips correctly.

## 5. Create a ticket

We need a category, priority, and (optionally) location id first. If they don't already
exist:
- `GET /categories` — note an existing `id` (e.g. `1` for "Hardware"), or `POST /categories`
  with `{"name": "Hardware"}` if the list is empty.
- `GET /priorities` — the four defaults (`Low`/`Medium`/`High`/`Critical`) should already
  exist from Step 2.
- `GET /locations` — see Step 11 if empty.

Expand **`POST /ticket-new`**, execute with:
```json
{
  "title": "Laptop does not power on",
  "description": "Employee's laptop shows no signs of life when the power button is pressed.",
  "location_id": 1,
  "category_id": 1,
  "priority_id": 3
}
```
The response is `201`, wrapped in `{"data": {...}, "msg": "Ticket created successfully"}`.
Point out: `status` is `"NEW"`, `ticket_number` follows the `IT-<year>-<sequence>` format,
`created_by` is the currently authenticated user (a Manager here, since Manager is allowed to
create tickets too — not just Employees), and `location`/`category`/`priority` are returned
as full nested objects, not just ids. **Copy the ticket's `id`** — every remaining step uses
it.

## 6. Assign a technician

Still authenticated as Manager. You'll need the technician's user id —
`GET /users?role_id=<technician's role id>` (or just `GET /users` and find `"username":
"technician"` in the list) to get it.

Expand **`PATCH /tickets/{ticket_id}/assign`**, fill in the ticket id, execute with:
```json
{"technician_id": <technician's id>}
```
Response (bare, `200`): `assigned_technician` is now populated, and `status` has
auto-advanced from `NEW` to `ASSIGNED` — point out this transition happens automatically as
part of assignment, not through the status endpoint.

## 7. Change status

Now log in as **Technician** (repeat Step 4 with `technician`/`Technician123!`, re-Authorize
with the new token).

Expand **`PATCH /tickets/{ticket_id}/status`**, execute with:
```json
{"status": "IN_PROGRESS"}
```
Point out: this only succeeded because this technician is the one assigned to the ticket, and
because `ASSIGNED → IN_PROGRESS` is a legal transition. Try setting `"status": "NEW"`
afterward to show a `409 Conflict` — that transition isn't allowed from `IN_PROGRESS`.

## 8. Upload an attachment

Still as Technician. Expand **`POST /tickets/{ticket_id}/attachments`**, fill in the ticket
id. This endpoint takes a real file (multipart upload, not JSON) — click **Choose File** and
pick any small `.png`/`.jpg`/`.pdf`/`.txt`/`.docx`/`.xlsx` file, then **Execute**.

Point out: the response's `original_filename` matches what you uploaded, but there is no
`stored_filename`/`file_path` in the response — the internal storage location is never
exposed. If you have terminal access handy, `ls backend/storage/attachments/` shows the file
saved under a random, unguessable name.

## 9. Add a comment

Expand **`POST /tickets/{ticket_id}/comments`**, execute with:
```json
{"content": "Diagnosed a dead battery - ordering a replacement."}
```

## 10. Show the history

Expand **`GET /tickets/{ticket_id}/history`**, execute with no body. This returns the full,
ordered audit trail for the ticket: `ticket_created` → `attachment_added` →
`assigned_technician` → `status` (twice, once for the auto-advance in Step 6 and once for
Step 7) → `comment_added` — each with who did it, when, and the old/new value. This is the
single best endpoint to show off for the "auditing" part of the project.

## 11. Show Locations

Log back in as **Administrator** (`admin` / `Admin123!`, or the `.env` password if the quirk
above applies).

1. `GET /locations` — show the list (including any deactivated ones — they're still
   returned, just not selectable for *new* tickets).
2. `POST /locations` with `{"title": "Branch Office - Ground Floor"}` — `201`.
3. `PATCH /locations/{id}` with `{"is_active": false}` on that new location — `200`,
   `is_active` is now `false`.
4. Try `POST /ticket-new` (or `PATCH /tickets/{id}`) with that now-deactivated location's
   `location_id` — `400 Bad Request`, `"Location not found or inactive"`. Point out: the
   ticket from Step 5, which already used a *different*, still-active location, is
   completely unaffected — deactivation only blocks *new* selection, never breaks existing
   data. That's the entire reason Locations are deactivated instead of deleted.

## 12. Demonstrate role permissions

A few quick, high-signal 403s to show the permission system is real, not just documented:

- **Log in as Employee.** Try `POST /locations` — `403 Forbidden`. Only Administrators may
  manage locations (Managers, who *can* manage Departments/Priorities/Categories, still get
  403 here too — worth calling out as the one deliberately stricter resource).
- **Still as Employee.** Try `PATCH /tickets/{ticket_id}/assign` on the ticket from Step 5 —
  `403 Forbidden`. Only Manager/Administrator may assign technicians.
- **Still as Employee.** Try `GET /tickets/{ticket_id}` for a ticket created by a *different*
  employee (create a second one quickly as Manager if needed, on behalf of someone else via
  `requester_user_id`) — `403 Forbidden`, distinct from `404` for a ticket that doesn't exist
  at all.
- **Log in as Manager.** Try `PATCH /users/{some other user's id}` with
  `{"first_name": "Test"}` — `403 Forbidden`. Managers can view every user but cannot edit
  anyone else's account; only Administrators can. Then show the same Manager successfully
  `PATCH /users/{their own id}` with `{"theme": "dark"}` — `200`, since editing your *own*
  safe fields is always allowed.

This closes the loop: authentication (Section 4), the full ticket lifecycle (Sections 5–10),
the newest feature end-to-end (Section 11), and the permission system enforcing exactly what
the documentation claims (Section 12).
