import enum


class TicketStatus(str, enum.Enum):
    """Lifecycle states a ticket can move through, per docs/database-design.md."""

    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_EMPLOYEE = "WAITING_FOR_EMPLOYEE"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# A ticket in one of these statuses is done - excluded from "open" counts
# (TicketRepository.count_high_priority_open, schemas.analytics's
# open_count derivation). Mirrors the frontend dashboard's own
# openStatuses set (frontend/src/pages/DashboardPage.tsx) so "open" means
# the same thing everywhere it's used.
TERMINAL_TICKET_STATUSES = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})


class InventoryTrackingType(str, enum.Enum):
    """Whether an InventoryItem row represents one physical, serial-numbered
    unit (SERIALIZED - a laptop, a monitor) or a SKU-level quantity of
    interchangeable stock (BULK - cables, mice). See InventoryItem's
    docstring for the full set of rules each tracking type enforces."""

    SERIALIZED = "SERIALIZED"
    BULK = "BULK"


class InventoryStatus(str, enum.Enum):
    """Lifecycle states an InventoryItem can be in.

    Shared by both tracking types rather than having two separate enums:
    SERIALIZED items may use all five values; BULK items are restricted to
    AVAILABLE/RETIRED only (enforced by ck_inventory_items_bulk_status) -
    RESERVED/IN_USE/IN_REPAIR describe a single physical unit's state, which
    doesn't apply to a SKU-level quantity row.
    """

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    IN_USE = "IN_USE"
    IN_REPAIR = "IN_REPAIR"
    RETIRED = "RETIRED"


class InventoryCondition(str, enum.Enum):
    """Physical condition of a SERIALIZED asset - independent of `status`
    (e.g. status=IN_USE, condition=DAMAGED are both true at once). Nullable
    and not meaningful for BULK stock."""

    NEW = "NEW"
    GOOD = "GOOD"
    FAIR = "FAIR"
    DAMAGED = "DAMAGED"
    BROKEN = "BROKEN"


class TicketInventoryUsageStatus(str, enum.Enum):
    """The current relationship between a ticket and an inventory item.

    This is NOT an audit trail (that's InventoryTransaction, Milestone 12) -
    a TicketInventoryUsage row only exists while it is true, and is deleted
    the moment it stops being true:

    - RESERVED: the item/quantity is held against this ticket but not yet
      used. Reversible via "release", which deletes the row.
    - CONSUMED: the item/quantity has actually been used to resolve this
      ticket (stock decremented / serialized item marked in use).
      Reversible only via the explicit "remove" (undo) action, which is
      restricted to Company Administrator - see TicketInventoryService.
    """

    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"


class InventoryTransactionType(str, enum.Enum):
    """The kind of event an InventoryTransaction row records - see that
    model's docstring for the full audit-trail design.

    CREATED/RESERVED/RELEASED/CONSUMED/CONSUME_UNDONE/STOCK_ADJUSTED/
    STATUS_CHANGED/HOLDER_CHANGED/LOCATION_CHANGED each carry their own
    precise, workflow-significant meaning. EDITED is the generic catch-all
    for every other simple field edit (name, manufacturer, model,
    serial_number, asset_tag, inventory_category_id, condition,
    minimum_stock, purchase_date, warranty_expiration, supplier,
    purchase_cost, invoice_number, image_path, notes) - one row per
    changed field, using field_name/old_value/new_value, the same
    approach TicketHistory already uses for ticket field edits.

    Deliberately no separate RETIRED type: retiring an asset is just a
    status change to RETIRED, captured by STATUS_CHANGED like any other
    manual status change - a dedicated type would be redundant.
    """

    CREATED = "CREATED"
    EDITED = "EDITED"
    STOCK_ADJUSTED = "STOCK_ADJUSTED"
    STATUS_CHANGED = "STATUS_CHANGED"
    HOLDER_CHANGED = "HOLDER_CHANGED"
    LOCATION_CHANGED = "LOCATION_CHANGED"
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"
    CONSUME_UNDONE = "CONSUME_UNDONE"
