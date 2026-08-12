import enum


class TicketStatus(str, enum.Enum):
    """Lifecycle states a ticket can move through, per docs/database-design.md."""

    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_EMPLOYEE = "WAITING_FOR_EMPLOYEE"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


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
