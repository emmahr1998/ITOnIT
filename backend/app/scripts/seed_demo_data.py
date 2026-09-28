"""DEVELOPMENT / DEMO ONLY - seeds a realistic, presentable dataset for the
professor demo (Milestone 14, Phase 14.4) on a dedicated Demo Company.

Run from the backend/ directory, after the roles/Default Company bootstrap:
    python -m app.scripts.seed_demo_data

This script is NOT an Alembic migration, is NEVER imported or run by
application startup (app/main.py never touches it), and must only ever be
run against a development/demo database - it creates a company, ticket, and
inventory dataset meant to be shown to an audience, not real production data.

Why a dedicated "ITOnIT Demo Co" (company_code DEMO001) rather than seeding
onto the Default Company (DEFAULT001, the one `create_demo_users.py`
populates): isolation. A presenter can run this script and demo it without
ever touching whatever a developer has been testing on DEFAULT001 - and
DEFAULT001's own data (created ad hoc across many earlier milestones) is not
curated for a live audience the way this dataset is. There is deliberately
no cleanup/teardown command for this dataset (see Phase 14.4's report on
why one was considered and not added - broad deletion of a "demo" company
is a real risk with too little benefit here); if it's ever no longer
needed, deactivate or remove it the same way any other company would be.
The company is created through the exact same CompanyService.register_company
path POST /companies/register uses - no parallel creation logic - so it
gets the same starter priorities/categories/location/department/inventory
categories every real company gets.

Idempotence: every entity below is looked up by a deterministic, human-chosen
name/title/username/asset_tag before being created, using the same
repository lookups the real services already use for their own uniqueness
checks (never a hardcoded primary key). Running this script again after it
has already completed makes no further changes at all - every check finds
its entity already present and skips it, and the summary printed at the end
reports "already existed" instead of creating a duplicate. Running it again
after a *partial* failure resumes correctly: whatever was already committed
(each step below commits through its own owning service, exactly like the
real API does) is found and skipped, and only what's still missing is
created - see PHASE_14_4 notes in this docstring's home report for why this
design was chosen over one large all-or-nothing transaction (this codebase's
services each own their own commit boundary; this script intentionally does
not fight that architecture).

What this script does NOT do, on purpose:
- It never edits or deletes anything on any *other* company (including
  DEFAULT001) - every lookup/write below is scoped to the Demo Company's own
  id, resolved dynamically by its company_code.
- It never inserts a row directly with a raw INSERT/ORM `add()` bypassing a
  service for anything a real service already knows how to create validly -
  tickets go through TicketService, comments through CommentService,
  attachments through AttachmentService (real bytes really written to disk
  via StorageService - never a database-only attachment row), inventory
  items through InventoryItemService, and every reserve/consume/release goes
  through TicketInventoryService so InventoryTransaction's append-only
  guarantee is preserved exactly as the real application enforces it.
- It never advances a ticket past the point the professor demo script
  (docs/PROFESSOR_DEMO_GUIDE.md) needs to still be able to demonstrate a
  live reserve→consume action itself - the "story ticket" (see
  _STORY_TICKET_TITLE below) is deliberately left with its Docking Station
  inventory item still AVAILABLE and unreserved.
"""

import sys
from pathlib import Path

# Not part of the `app` package's normal import surface when run directly -
# same convention as scripts/create_demo_users.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import date, timedelta  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.enums import (  # noqa: E402
    InventoryCondition,
    InventoryStatus,
    InventoryTrackingType,
    InventoryTransactionType,
    TicketStatus,
)
from app.models.user import User  # noqa: E402
from app.repositories.category import CategoryRepository  # noqa: E402
from app.repositories.company import CompanyRepository  # noqa: E402
from app.repositories.department import DepartmentRepository  # noqa: E402
from app.repositories.inventory_category import InventoryCategoryRepository  # noqa: E402
from app.repositories.inventory_item import InventoryItemRepository  # noqa: E402
from app.repositories.location import LocationRepository  # noqa: E402
from app.repositories.priority import PriorityRepository  # noqa: E402
from app.repositories.role import RoleRepository  # noqa: E402
from app.repositories.ticket import TicketRepository  # noqa: E402
from app.repositories.user import UserRepository  # noqa: E402
from app.schemas.company import CompanyRegisterRequest  # noqa: E402
from app.schemas.department import DepartmentCreate  # noqa: E402
from app.schemas.inventory_item import InventoryItemCreate  # noqa: E402
from app.schemas.location import LocationCreate  # noqa: E402
from app.schemas.ticket import TicketNewCreate  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services.attachment_service import AttachmentService  # noqa: E402
from app.services.comment_service import CommentService  # noqa: E402
from app.services.company_service import CompanyCodeConflictError, CompanyService  # noqa: E402
from app.services.inventory_item_service import InventoryItemService  # noqa: E402
from app.services.inventory_transaction_service import InventoryTransactionService  # noqa: E402
from app.services.ticket_inventory_service import TicketInventoryService  # noqa: E402
from app.services.ticket_service import TicketService  # noqa: E402
from app.services.user_service import UserService  # noqa: E402

# ---------------------------------------------------------------------------
# Demo company + demo users. Credentials here are DEVELOPMENT/DEMO ONLY -
# never real, never used anywhere but a local/demo database, and safe to
# publish in docs/PROFESSOR_DEMO_GUIDE.md exactly like create_demo_users.py's
# own accounts already are.
# ---------------------------------------------------------------------------

DEMO_COMPANY_CODE = "DEMO001"
DEMO_COMPANY_NAME = "ITOnIT Demo Co"

_ADMIN = {
    "username": "admin",
    "first_name": "Dana",
    "last_name": "Admin",
    "email": "admin@itonit-demo.local",
    "password": "DemoAdmin123!",
}
_TECHNICIAN = {
    "username": "technician",
    "first_name": "Taylor",
    "last_name": "Tech",
    "email": "technician@itonit-demo.local",
    "password": "Technician123!",
    "role_name": "Technician",
    "department_title": "IT",
}
_EMPLOYEE = {
    "username": "employee",
    "first_name": "Priya",
    "last_name": "Employee",
    "email": "employee@itonit-demo.local",
    "password": "Employee123!",
    "role_name": "Employee",
    "department_title": "General",
}
_EMPLOYEE_2 = {
    "username": "employee2",
    "first_name": "Sam",
    "last_name": "Rivera",
    "email": "employee2@itonit-demo.local",
    "password": "Employee2Pass123!",
    "role_name": "Employee",
    "department_title": "Sales",
}

_EXTRA_DEPARTMENTS = ["IT", "Sales"]  # "General" already exists from registration
_EXTRA_LOCATIONS = ["Remote / Home Office"]  # "Head Office" already exists from registration

_STORY_TICKET_TITLE = "Docking station not recognized - external monitor won't display"


def _get_or_register_company(db) -> tuple[object, bool]:
    """Returns (company, was_created)."""
    company_repository = CompanyRepository(db)
    company = company_repository.get_by_code(DEMO_COMPANY_CODE)
    if company is not None:
        return company, False

    company_service = CompanyService(db)
    try:
        admin = company_service.register_company(
            CompanyRegisterRequest(
                company_name=DEMO_COMPANY_NAME,
                company_code=DEMO_COMPANY_CODE,
                first_name=_ADMIN["first_name"],
                last_name=_ADMIN["last_name"],
                username=_ADMIN["username"],
                email=_ADMIN["email"],
                password=_ADMIN["password"],
            )
        )
    except CompanyCodeConflictError:
        # Lost a race with a concurrent run - fetch what the other run created.
        company = company_repository.get_by_code(DEMO_COMPANY_CODE)
        if company is None:  # pragma: no cover - should be unreachable
            raise
        return company, False
    return admin.company, True


def _get_or_create_department(db, company_id: int, title: str):
    repository = DepartmentRepository(db, company_id)
    existing = repository.get_by_title(title)
    if existing is not None:
        return existing, False
    from app.services.department_service import DepartmentService

    department = DepartmentService(db, company_id).create_department(DepartmentCreate(title=title))
    return department, True


def _get_or_create_location(db, company_id: int, title: str):
    repository = LocationRepository(db, company_id)
    existing = repository.get_by_title(title)
    if existing is not None:
        return existing, False
    from app.services.location_service import LocationService

    location = LocationService(db, company_id).create_location(LocationCreate(title=title))
    return location, True


def _get_or_create_user(
    db, company_id: int, spec: dict, role_id: int, department_id: int | None
) -> tuple[User, bool]:
    user_repository = UserRepository(db, company_id)
    existing = user_repository.get_by_username(spec["username"])
    if existing is not None:
        return existing, False

    user_service = UserService(db, company_id)
    user = user_service.create_user(
        UserCreate(
            username=spec["username"],
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            email=spec["email"],
            department_id=department_id,
            password=spec["password"],
            role_id=role_id,
        )
    )
    return user, True


def _get_or_create_inventory_item(
    db, company_id: int, current_user: User, *, spec: dict
) -> tuple[object, bool]:
    item_repository = InventoryItemRepository(db, company_id)
    if spec.get("asset_tag"):
        existing = item_repository.get_by_asset_tag(spec["asset_tag"])
        if existing is not None:
            return existing, False
    else:
        # BULK items here are untagged - matched by name instead (small,
        # curated catalog; a linear scan is fine and avoids needing a new
        # by-name lookup on the repository just for this script).
        for item in item_repository.get_all():
            if item.name == spec["name"]:
                return item, False

    service = InventoryItemService(db, company_id)
    item = service.create_item(
        InventoryItemCreate(
            inventory_category_id=spec["inventory_category_id"],
            name=spec["name"],
            tracking_type=spec["tracking_type"],
            status=spec.get("status", InventoryStatus.AVAILABLE),
            condition=spec.get("condition"),
            asset_tag=spec.get("asset_tag"),
            manufacturer=spec.get("manufacturer"),
            model=spec.get("model"),
            stock_quantity=spec.get("stock_quantity"),
            minimum_stock=spec.get("minimum_stock"),
            current_location_id=spec.get("current_location_id"),
            current_holder_user_id=spec.get("current_holder_user_id"),
            purchase_date=spec.get("purchase_date"),
            warranty_expiration=spec.get("warranty_expiration"),
            supplier=spec.get("supplier"),
        ),
        current_user,
    )
    return item, True


def main() -> None:
    db = SessionLocal()
    created_counts: dict[str, int] = {}
    skipped_counts: dict[str, int] = {}

    def note(label: str, was_created: bool) -> None:
        bucket = created_counts if was_created else skipped_counts
        bucket[label] = bucket.get(label, 0) + 1

    try:
        company, company_created = _get_or_register_company(db)
        note("company", company_created)
        company_id = company.id
        print(
            f"Demo company: {DEMO_COMPANY_CODE!r} (id={company_id}) - "
            + ("created" if company_created else "already existed")
        )

        role_repository = RoleRepository(db)
        technician_role = role_repository.get_by_name("Technician")
        employee_role = role_repository.get_by_name("Employee")
        if technician_role is None or employee_role is None:
            raise RuntimeError(
                "Technician/Employee roles are not seeded - run "
                "`python -m app.scripts.seed_initial_data` first."
            )

        # ---- reference data already seeded by registration -----------------
        category_repository = CategoryRepository(db, company_id)
        priority_repository = PriorityRepository(db, company_id)
        inventory_category_repository = InventoryCategoryRepository(db, company_id)
        categories = {c.name: c for c in category_repository.get_all()}
        priorities = {p.title: p for p in priority_repository.get_all()}
        inventory_categories = {c.name: c for c in inventory_category_repository.get_all()}
        for required in ("Hardware", "Software", "Network", "Account Access", "Other"):
            if required not in categories:
                raise RuntimeError(
                    f"Expected starter category {required!r} missing on the demo company - "
                    "registration's starter-data seeding may have changed."
                )
        head_office = LocationRepository(db, company_id).get_by_title("Head Office")
        if head_office is None:
            raise RuntimeError("Expected starter location 'Head Office' missing.")

        # ---- extra departments/locations for realistic variety --------------
        departments = {}
        for title in ["General", *_EXTRA_DEPARTMENTS]:
            dept, dept_created = _get_or_create_department(db, company_id, title)
            departments[title] = dept
            note(f"department:{title}", dept_created)

        locations = {"Head Office": head_office}
        for title in _EXTRA_LOCATIONS:
            loc, loc_created = _get_or_create_location(db, company_id, title)
            locations[title] = loc
            note(f"location:{title}", loc_created)

        # ---- demo users -----------------------------------------------------
        admin_user = UserRepository(db, company_id).get_by_username(_ADMIN["username"])
        note("user:admin", False)  # created as part of registration above, never here

        technician_user, tech_created = _get_or_create_user(
            db, company_id, _TECHNICIAN, technician_role.id, departments["IT"].id
        )
        note("user:technician", tech_created)

        employee_user, emp1_created = _get_or_create_user(
            db, company_id, _EMPLOYEE, employee_role.id, departments["General"].id
        )
        note("user:employee", emp1_created)

        employee2_user, emp2_created = _get_or_create_user(
            db, company_id, _EMPLOYEE_2, employee_role.id, departments["Sales"].id
        )
        note("user:employee2", emp2_created)

        # ---- inventory catalog ------------------------------------------------
        today = date.today()
        inventory_specs = [
            {
                "key": "laptop_1",
                "name": "Dell Latitude 5540",
                "tracking_type": InventoryTrackingType.SERIALIZED,
                "asset_tag": "DEMO-LT-001",
                "inventory_category_id": inventory_categories["Laptop"].id,
                "status": InventoryStatus.AVAILABLE,
                "condition": InventoryCondition.GOOD,
                "manufacturer": "Dell",
                "model": "Latitude 5540",
                "current_location_id": locations["Head Office"].id,
            },
            {
                "key": "monitor_1",
                "name": "Dell 24-inch Monitor P2422H",
                "tracking_type": InventoryTrackingType.SERIALIZED,
                "asset_tag": "DEMO-MON-001",
                "inventory_category_id": inventory_categories["Monitor"].id,
                "status": InventoryStatus.AVAILABLE,
                "condition": InventoryCondition.GOOD,
                "manufacturer": "Dell",
                "model": "P2422H",
                "current_location_id": locations["Head Office"].id,
            },
            {
                "key": "laptop_2_in_use",
                "name": "Dell Latitude 5540 (Unit 2)",
                "tracking_type": InventoryTrackingType.SERIALIZED,
                "asset_tag": "DEMO-LT-002",
                "inventory_category_id": inventory_categories["Laptop"].id,
                "status": InventoryStatus.IN_USE,
                "condition": InventoryCondition.GOOD,
                "manufacturer": "Dell",
                "model": "Latitude 5540",
                "current_holder_user_id": employee2_user.id,
            },
            {
                "key": "dock_story",
                "name": "Dell WD19 Docking Station",
                "tracking_type": InventoryTrackingType.SERIALIZED,
                "asset_tag": "DEMO-DOCK-001",
                "inventory_category_id": inventory_categories["Dock"].id,
                "status": InventoryStatus.AVAILABLE,
                "condition": InventoryCondition.NEW,
                "manufacturer": "Dell",
                "model": "WD19",
                "current_location_id": locations["Head Office"].id,
                "purchase_date": today - timedelta(days=300),
                "warranty_expiration": today + timedelta(days=20),
                "supplier": "Demo IT Supplier Co.",
            },
            {
                "key": "cable_bulk",
                "name": "USB-C Cable 2m",
                "tracking_type": InventoryTrackingType.BULK,
                "inventory_category_id": inventory_categories["Cable"].id,
                "status": InventoryStatus.AVAILABLE,
                "stock_quantity": 50,
                "minimum_stock": 10,
            },
            {
                "key": "mouse_low_stock",
                "name": "Wireless Mouse",
                "tracking_type": InventoryTrackingType.BULK,
                "inventory_category_id": inventory_categories["Mouse"].id,
                "status": InventoryStatus.AVAILABLE,
                "stock_quantity": 5,
                "minimum_stock": 10,
            },
            {
                "key": "keyboard_bulk",
                "name": "Wireless Keyboard",
                "tracking_type": InventoryTrackingType.BULK,
                "inventory_category_id": inventory_categories["Keyboard"].id,
                "status": InventoryStatus.AVAILABLE,
                "stock_quantity": 20,
                "minimum_stock": 5,
            },
        ]
        inventory_items = {}
        for spec in inventory_specs:
            item, item_created = _get_or_create_inventory_item(
                db, company_id, admin_user, spec=spec
            )
            inventory_items[spec["key"]] = item
            note(f"inventory_item:{spec['key']}", item_created)

        # ---- tickets -----------------------------------------------------------
        ticket_service = TicketService(db, company_id)
        comment_service = CommentService(db, company_id)
        attachment_service = AttachmentService(db, company_id)
        ticket_inventory_service = TicketInventoryService(db, company_id)
        inventory_transaction_service = InventoryTransactionService(db, company_id)

        existing_tickets_by_title = {
            t.title: t for t in TicketRepository(db, company_id).get_with_filters()
        }

        def create_ticket(
            *, title, description, requester, category_name, priority_title, location=None
        ):
            existing = existing_tickets_by_title.get(title)
            if existing is not None:
                return existing, False
            ticket = ticket_service.create_ticket_new(
                requester,
                TicketNewCreate(
                    title=title,
                    description=description,
                    location_id=location.id if location else None,
                    category_id=categories[category_name].id,
                    priority_id=priorities[priority_title].id,
                ),
            )
            existing_tickets_by_title[title] = ticket
            return ticket, True

        def advance(ticket, *, assign_to=None, statuses: list[TicketStatus] = ()):
            if assign_to is not None:
                ticket_service.assign_technician(admin_user, ticket.id, assign_to.id)
            for status in statuses:
                ticket_service.change_status(technician_user, ticket.id, status)

        # 1. NEW
        t1, c1 = create_ticket(
            title="Cannot install printer driver on new laptop",
            description=(
                "New laptop can't find the shared office printer. Driver install from the "
                "vendor site fails with an unknown error."
            ),
            requester=employee_user,
            category_name="Software",
            priority_title="Low",
        )
        note("ticket:printer_driver", c1)

        # 2. NEW
        t2, c2 = create_ticket(
            title="Locked out of VPN after password reset",
            description="Reset my password this morning and now the VPN client rejects it every time.",
            requester=employee2_user,
            category_name="Account Access",
            priority_title="Medium",
            location=locations["Remote / Home Office"],
        )
        note("ticket:vpn_lockout", c2)

        # 3. ASSIGNED
        t3, c3 = create_ticket(
            title="Conference room Wi-Fi keeps disconnecting",
            description="Wi-Fi in the main conference room drops every few minutes during calls.",
            requester=employee_user,
            category_name="Network",
            priority_title="High",
            location=locations["Head Office"],
        )
        if c3:
            advance(t3, assign_to=technician_user)
            comment_service.add_comment(
                technician_user, t3.id, "Looking into the access point logs for that room now."
            )
        note("ticket:conference_wifi", c3)

        # 4. ASSIGNED
        t4, c4 = create_ticket(
            title="Second monitor not detected",
            description="External monitor worked yesterday, today the laptop doesn't detect it at all.",
            requester=employee2_user,
            category_name="Hardware",
            priority_title="Medium",
            location=locations["Head Office"],
        )
        if c4:
            advance(t4, assign_to=technician_user)
        note("ticket:second_monitor", c4)

        # 5. IN_PROGRESS - historical BULK reserve -> release
        t5, c5 = create_ticket(
            title="Workstation randomly shuts down",
            description="Desktop shuts down without warning several times a day, no error shown.",
            requester=employee_user,
            category_name="Hardware",
            priority_title="Critical",
            location=locations["Head Office"],
        )
        if c5:
            advance(t5, assign_to=technician_user, statuses=[TicketStatus.IN_PROGRESS])
            comment_service.add_comment(
                technician_user,
                t5.id,
                "Suspect a failing power supply - grabbing a replacement cable to rule out a "
                "simpler cause first.",
            )
        note("ticket:workstation_shutdown", c5)
        cable_item = inventory_items["cable_bulk"]
        released_already, _ = inventory_transaction_service.list_company_transactions(
            inventory_item_id=cable_item.id,
            ticket_id=t5.id,
            transaction_type=InventoryTransactionType.RELEASED,
        )
        if not released_already:
            usage = ticket_inventory_service.reserve(technician_user, t5.id, cable_item.id, 3)
            ticket_inventory_service.release(technician_user, t5.id, usage.id)
            note("inventory_txn:cable_reserve_release", True)
        else:
            note("inventory_txn:cable_reserve_release", False)

        # 6. IN_PROGRESS
        t6, c6 = create_ticket(
            title="Email client crashes on startup",
            description="Outlook crashes immediately after the splash screen since this morning's update.",
            requester=employee2_user,
            category_name="Software",
            priority_title="Medium",
            location=locations["Remote / Home Office"],
        )
        if c6:
            advance(t6, assign_to=technician_user, statuses=[TicketStatus.IN_PROGRESS])
        note("ticket:email_crash", c6)

        # 7. WAITING_FOR_EMPLOYEE
        t7, c7 = create_ticket(
            title="Requesting access to shared drive",
            description="Need read/write access to the shared project drive for the new campaign.",
            requester=employee_user,
            category_name="Account Access",
            priority_title="Low",
        )
        if c7:
            advance(
                t7,
                assign_to=technician_user,
                statuses=[TicketStatus.IN_PROGRESS, TicketStatus.WAITING_FOR_EMPLOYEE],
            )
            comment_service.add_comment(
                technician_user,
                t7.id,
                "Submitted the access request to IT security - waiting on manager approval "
                "from your side before I can grant it.",
            )
        note("ticket:shared_drive_access", c7)

        # 8. RESOLVED - historical BULK reserve -> consume
        t8, c8 = create_ticket(
            title="Replace worn out keyboard",
            description="Keys are sticking on my keyboard, requesting a replacement.",
            requester=employee2_user,
            category_name="Hardware",
            priority_title="Low",
            location=locations["Head Office"],
        )
        if c8:
            advance(t8, assign_to=technician_user, statuses=[TicketStatus.IN_PROGRESS])
        note("ticket:worn_keyboard", c8)
        keyboard_item = inventory_items["keyboard_bulk"]
        consumed_already, _ = inventory_transaction_service.list_company_transactions(
            inventory_item_id=keyboard_item.id,
            ticket_id=t8.id,
            transaction_type=InventoryTransactionType.CONSUMED,
        )
        if not consumed_already:
            usage = ticket_inventory_service.reserve(technician_user, t8.id, keyboard_item.id, 2)
            ticket_inventory_service.consume(technician_user, t8.id, usage.id)
            note("inventory_txn:keyboard_reserve_consume", True)
        else:
            note("inventory_txn:keyboard_reserve_consume", False)
        if c8:
            ticket_service.change_status(technician_user, t8.id, TicketStatus.RESOLVED)

        # 9. RESOLVED
        t9, c9 = create_ticket(
            title="Docking station intermittent connection - resolved after firmware update",
            description="External display through the docking station drops connection randomly.",
            requester=employee_user,
            category_name="Network",
            priority_title="High",
            location=locations["Head Office"],
        )
        if c9:
            advance(
                t9,
                assign_to=technician_user,
                statuses=[TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED],
            )
            comment_service.add_comment(
                technician_user, t9.id, "Firmware update resolved it - monitored for two days, stable."
            )
        note("ticket:dock_firmware", c9)

        # 10. CLOSED
        t10, c10 = create_ticket(
            title="General IT onboarding questions",
            description="A few questions about available equipment and IT policies for a new starter.",
            requester=employee2_user,
            category_name="Other",
            priority_title="Medium",
        )
        if c10:
            advance(
                t10,
                assign_to=technician_user,
                statuses=[TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED],
            )
        note("ticket:onboarding_questions", c10)

        # 11. CLOSED
        t11, c11 = create_ticket(
            title="Reinstall design software after OS update",
            description="Design software stopped launching after the latest OS update.",
            requester=employee_user,
            category_name="Software",
            priority_title="Low",
            location=locations["Head Office"],
        )
        if c11:
            advance(
                t11,
                assign_to=technician_user,
                statuses=[TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED],
            )
        note("ticket:design_software_reinstall", c11)

        # 12. STORY TICKET - IN_PROGRESS, inventory action left fully live.
        story, story_created = create_ticket(
            title=_STORY_TICKET_TITLE,
            description=(
                "Since this morning the docking station no longer drives the external monitor - "
                "laptop screen works fine on its own, but nothing shows up on the second display "
                "when docked."
            ),
            requester=employee_user,
            category_name="Hardware",
            priority_title="High",
            location=locations["Head Office"],
        )
        if story_created:
            advance(story, assign_to=technician_user, statuses=[TicketStatus.IN_PROGRESS])
            comment_service.add_comment(
                technician_user,
                story.id,
                "Confirmed the dock's firmware is current and the cable is fine - the docking "
                "station unit itself looks to be at fault. Pulling a replacement from inventory.",
            )
            comment_service.add_comment(
                employee_user,
                story.id,
                "Thanks for the update - happy to swap it whenever is convenient.",
            )
            attachment_service.upload_attachment(
                technician_user,
                story.id,
                "diagnostic-log.txt",
                "text/plain",
                (
                    b"ITOnIT diagnostic export\n"
                    b"Device: Dell Latitude 5540\n"
                    b"Dock firmware: up to date\n"
                    b"Display cable: tested OK on a known-good dock\n"
                    b"Conclusion: docking station unit suspected faulty\n"
                ),
            )
        note("ticket:story", story_created)

        print("\nStory ticket for the live demo:")
        print(f"  Ticket number: {story.ticket_number}")
        print(f"  Title:         {story.title}")
        print(
            "  Live action:   reserve, then consume, "
            f"{inventory_items['dock_story'].name!r} "
            f"(asset tag {inventory_items['dock_story'].asset_tag}) against this ticket."
        )

        print("\n--- Created this run ---")
        for label, count in sorted(created_counts.items()):
            print(f"  {label}: {count}")
        print("--- Already existed (skipped) ---")
        for label, count in sorted(skipped_counts.items()):
            print(f"  {label}: {count}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
