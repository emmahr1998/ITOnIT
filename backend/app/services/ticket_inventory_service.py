from sqlalchemy.orm import Session

from app.models.enums import (
    InventoryStatus,
    InventoryTrackingType,
    InventoryTransactionType,
    TicketInventoryUsageStatus,
)
from app.models.inventory_item import InventoryItem
from app.models.ticket import Ticket
from app.models.ticket_inventory_usage import TicketInventoryUsage
from app.models.user import User
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.ticket import TicketRepository
from app.repositories.ticket_inventory_usage import TicketInventoryUsageRepository
from app.services.history_service import HistoryService
from app.services.inventory_transaction_service import InventoryTransactionService

TECHNICIAN_ROLE_NAME = "Technician"
_MANAGE_ROLE_NAMES = ("Company Administrator",)


class TicketInventoryTicketNotFoundError(Exception):
    """Raised when the ticket id does not exist (or not in the caller's own company)."""


class TicketInventoryPermissionError(Exception):
    """Raised when a Technician who is not assigned to this ticket tries to act on it."""


class TicketInventoryUsageNotFoundError(Exception):
    """Raised when a usage id does not exist, or does not belong to the given ticket."""


class TicketInventoryItemNotFoundError(Exception):
    """Raised when inventory_item_id does not reference an item in the caller's own company."""


class TicketInventoryCategoryInactiveError(Exception):
    """Raised when the referenced item's inventory category has been deactivated."""


class TicketInventoryItemRetiredError(Exception):
    """Raised when trying to reserve an item whose status is RETIRED."""


class TicketInventoryItemUnavailableError(Exception):
    """Raised when trying to reserve a SERIALIZED item that is not AVAILABLE
    (already reserved/in use/in repair - by this ticket or another one)."""


class TicketInventoryDuplicateReservationError(Exception):
    """Raised when the same item is already attached (reserved or consumed) to this ticket."""


class TicketInventoryInsufficientStockError(Exception):
    """Raised when a BULK reservation would exceed the item's available stock
    (stock_quantity - reserved_quantity)."""


class TicketInventoryValidationError(Exception):
    """Raised for a malformed request the schema layer can't catch alone
    (e.g. quantity != 1 for a SERIALIZED item)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TicketInventoryStateError(Exception):
    """Raised when the requested action doesn't match the usage row's
    current status (e.g. consuming a row that's already CONSUMED)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _describe(item: InventoryItem, quantity: int) -> str:
    """Human-readable "what" for a TicketHistory entry - matches how
    TicketService.assign_technician already stores names, not raw ids,
    in TicketHistory old_value/new_value."""
    if item.tracking_type == InventoryTrackingType.SERIALIZED:
        return f"{item.name} ({item.asset_tag})" if item.asset_tag else item.name
    return f"{quantity} × {item.name}"


class TicketInventoryService:
    """Owns the Ticket <-> Inventory integration: reserve/release/consume/
    remove, and the InventoryItem side effects each transition applies.

    TicketInventoryUsage represents the CURRENT relationship only. Every
    write here also records an InventoryTransaction row (Phase 12.1) via
    InventoryTransactionService - RESERVED/RELEASED/CONSUMED/
    CONSUME_UNDONE, one per business event, never a duplicate
    STATUS_CHANGED/HOLDER_CHANGED row for the same event (those dedicated
    types are reserved for manual, non-ticket-workflow edits made through
    InventoryItemService - see that service's docstring). A row is
    created on reserve and deleted on release or remove (undo); consume
    flips it from RESERVED to CONSUMED in place.

    Ticket-related actions (reserve/release/consume/remove) also write a
    lightweight, narrative TicketHistory entry via HistoryService, exactly
    like every other ticket mutation in this codebase (e.g. CommentService
    already writes both a Comment and a TicketHistory row for one action) -
    InventoryTransaction is the inventory-centric source of truth,
    TicketHistory stays the ticket-facing timeline. release_all_for_ticket
    (the ticket-deletion cleanup path) does NOT write TicketHistory: the
    ticket and all its history rows are being deleted in the same request
    moments later, so a history entry there would be pointless.

    Ticket-level access follows the same pattern as
    TicketService.change_status: the route enforces the role gate
    (Technician/Company Administrator only - Employee never reaches these
    routes at all), and this service enforces ticket *ownership* for
    Technician (must be the assigned technician) - Company Administrator
    has no such restriction.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    It scopes every repository this service touches, so a payload
    referencing another company's ticket/inventory item can never resolve
    to a real row here (mirrors InventoryItemService's own docstring on
    this point).
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        usage_repository: TicketInventoryUsageRepository | None = None,
        item_repository: InventoryItemRepository | None = None,
        ticket_repository: TicketRepository | None = None,
        inventory_transaction_service: InventoryTransactionService | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._usage_repository = (
            usage_repository
            if usage_repository is not None
            else TicketInventoryUsageRepository(db, company_id)
        )
        self._item_repository = (
            item_repository if item_repository is not None else InventoryItemRepository(db, company_id)
        )
        self._ticket_repository = (
            ticket_repository if ticket_repository is not None else TicketRepository(db, company_id)
        )
        self._inventory_transaction_service = (
            inventory_transaction_service
            if inventory_transaction_service is not None
            else InventoryTransactionService(db, company_id)
        )
        self._history_service = (
            history_service if history_service is not None else HistoryService(db, company_id)
        )

    # ---- ownership -----------------------------------------------------

    def _get_ticket_for_action(self, ticket_id: int, current_user: User) -> Ticket:
        ticket = self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketInventoryTicketNotFoundError
        if (
            current_user.role.name == TECHNICIAN_ROLE_NAME
            and ticket.assigned_technician_id != current_user.id
        ):
            raise TicketInventoryPermissionError
        return ticket

    def _get_owned_usage(self, ticket_id: int, usage_id: int) -> TicketInventoryUsage:
        usage = self._usage_repository.get_by_id(usage_id)
        if usage is None or usage.ticket_id != ticket_id:
            raise TicketInventoryUsageNotFoundError
        return usage

    # ---- reads -----------------------------------------------------------

    def list_for_ticket(self, current_user: User, ticket_id: int) -> list[TicketInventoryUsage]:
        ticket = self._get_ticket_for_action(ticket_id, current_user)
        return self._usage_repository.list_for_ticket(ticket.id)

    # ---- item eligibility --------------------------------------------------

    def _get_reservable_item_or_raise(self, inventory_item_id: int) -> InventoryItem:
        item = self._item_repository.get_by_id(inventory_item_id)
        if item is None:
            raise TicketInventoryItemNotFoundError
        if not item.inventory_category.is_active:
            raise TicketInventoryCategoryInactiveError
        if item.status == InventoryStatus.RETIRED:
            raise TicketInventoryItemRetiredError
        return item

    # ---- writes ------------------------------------------------------------

    def reserve(
        self, current_user: User, ticket_id: int, inventory_item_id: int, quantity: int
    ) -> TicketInventoryUsage:
        ticket = self._get_ticket_for_action(ticket_id, current_user)
        item = self._get_reservable_item_or_raise(inventory_item_id)
        existing = self._usage_repository.get_existing(ticket.id, inventory_item_id)

        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            if quantity != 1:
                raise TicketInventoryValidationError(
                    "quantity must be 1 for a serialized item"
                )
            if existing is not None:
                raise TicketInventoryDuplicateReservationError
            if item.status != InventoryStatus.AVAILABLE:
                raise TicketInventoryItemUnavailableError
            item.status = InventoryStatus.RESERVED
            item.reserved_quantity = 1
            usage_quantity = 1
        else:
            available = item.stock_quantity - item.reserved_quantity
            if quantity > available:
                raise TicketInventoryInsufficientStockError
            if existing is not None:
                if existing.status == TicketInventoryUsageStatus.CONSUMED:
                    # Known Version 1 limitation, approved as-is: only one
                    # usage row may exist per (ticket, item), so a BULK item
                    # already consumed on this ticket can't be reserved
                    # again until a Company Administrator undoes that
                    # consumption first (see remove()) - see
                    # TicketInventoryUsage's docstring for the full
                    # rationale and the Milestone 12 follow-up.
                    raise TicketInventoryDuplicateReservationError
                existing.quantity += quantity
                item.reserved_quantity += quantity
                self._item_repository.update(item)
                self._usage_repository.update(existing)
                self._inventory_transaction_service.record(
                    inventory_item=item,
                    performed_by=current_user,
                    transaction_type=InventoryTransactionType.RESERVED,
                    ticket=ticket,
                    quantity_delta=quantity,
                )
                self._history_service.record(
                    ticket.id, current_user, "inventory", None, f"Reserved {_describe(item, quantity)}"
                )
                self._db.commit()
                return existing
            item.reserved_quantity += quantity
            usage_quantity = quantity

        usage = TicketInventoryUsage(
            company_id=self._company_id,
            ticket_id=ticket.id,
            inventory_item_id=item.id,
            quantity=usage_quantity,
            status=TicketInventoryUsageStatus.RESERVED,
            selected_by_user_id=current_user.id,
        )
        usage.ticket = ticket
        usage.inventory_item = item
        usage.selected_by = current_user
        self._item_repository.update(item)
        self._usage_repository.create(usage)
        self._inventory_transaction_service.record(
            inventory_item=item,
            performed_by=current_user,
            transaction_type=InventoryTransactionType.RESERVED,
            ticket=ticket,
            quantity_delta=usage_quantity,
            field_name="status" if item.tracking_type == InventoryTrackingType.SERIALIZED else None,
            old_value="AVAILABLE" if item.tracking_type == InventoryTrackingType.SERIALIZED else None,
            new_value="RESERVED" if item.tracking_type == InventoryTrackingType.SERIALIZED else None,
        )
        self._history_service.record(
            ticket.id, current_user, "inventory", None, f"Reserved {_describe(item, usage_quantity)}"
        )
        self._db.commit()
        return usage

    @staticmethod
    def _revert_reserved(item: InventoryItem, usage: TicketInventoryUsage) -> None:
        """Undo a RESERVED usage row's hold on `item` - shared by release()
        and release_all_for_ticket()."""
        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            item.status = InventoryStatus.AVAILABLE
            item.reserved_quantity = 0
        else:
            item.reserved_quantity -= usage.quantity

    @staticmethod
    def _revert_consumed(item: InventoryItem, usage: TicketInventoryUsage) -> None:
        """Undo a CONSUMED usage row's effect on `item` - shared by
        remove() and release_all_for_ticket()."""
        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            item.status = InventoryStatus.AVAILABLE
            item.current_holder_user_id = None
            item.current_holder = None
            item.reserved_quantity = 0
        else:
            item.stock_quantity += usage.quantity

    def release(self, current_user: User, ticket_id: int, usage_id: int) -> None:
        ticket = self._get_ticket_for_action(ticket_id, current_user)
        usage = self._get_owned_usage(ticket.id, usage_id)
        if usage.status != TicketInventoryUsageStatus.RESERVED:
            raise TicketInventoryStateError("Only a reserved item can be released")

        item = usage.inventory_item
        is_serialized = item.tracking_type == InventoryTrackingType.SERIALIZED
        self._revert_reserved(item, usage)
        self._item_repository.update(item)
        self._inventory_transaction_service.record(
            inventory_item=item,
            performed_by=current_user,
            transaction_type=InventoryTransactionType.RELEASED,
            ticket=ticket,
            quantity_delta=-1 if is_serialized else -usage.quantity,
            field_name="status" if is_serialized else None,
            old_value="RESERVED" if is_serialized else None,
            new_value="AVAILABLE" if is_serialized else None,
        )
        self._history_service.record(
            ticket.id, current_user, "inventory", None, f"Released {_describe(item, usage.quantity)}"
        )
        self._usage_repository.delete(usage)
        self._db.commit()

    def consume(self, current_user: User, ticket_id: int, usage_id: int) -> TicketInventoryUsage:
        ticket = self._get_ticket_for_action(ticket_id, current_user)
        usage = self._get_owned_usage(ticket.id, usage_id)
        if usage.status != TicketInventoryUsageStatus.RESERVED:
            raise TicketInventoryStateError("Only a reserved item can be consumed")

        item = usage.inventory_item
        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            item.status = InventoryStatus.IN_USE
            item.reserved_quantity = 0
            item.current_holder_user_id = ticket.created_by_user_id
            item.current_holder = ticket.created_by
            quantity_delta = None
            notes = (
                f"Status RESERVED→IN_USE; holder assigned to "
                f"{ticket.created_by.first_name} {ticket.created_by.last_name}"
            )
        else:
            if usage.quantity > item.stock_quantity:
                raise TicketInventoryInsufficientStockError
            item.stock_quantity -= usage.quantity
            item.reserved_quantity -= usage.quantity
            quantity_delta = -usage.quantity
            notes = None

        usage.status = TicketInventoryUsageStatus.CONSUMED
        self._item_repository.update(item)
        self._usage_repository.update(usage)
        self._inventory_transaction_service.record(
            inventory_item=item,
            performed_by=current_user,
            transaction_type=InventoryTransactionType.CONSUMED,
            ticket=ticket,
            quantity_delta=quantity_delta,
            notes=notes,
        )
        self._history_service.record(
            ticket.id, current_user, "inventory", None, f"Consumed {_describe(item, usage.quantity)}"
        )
        self._db.commit()
        return usage

    def remove(self, current_user: User, ticket_id: int, usage_id: int) -> None:
        """Undo a CONSUMED usage row - restricted to Company Administrator
        at the route (a stock-correcting action, more privileged than the
        Technician-reachable reserve/release/consume)."""
        ticket = self._get_ticket_for_action(ticket_id, current_user)
        usage = self._get_owned_usage(ticket.id, usage_id)
        if usage.status != TicketInventoryUsageStatus.CONSUMED:
            raise TicketInventoryStateError("Only a consumed item can be removed")

        item = usage.inventory_item
        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            quantity_delta = None
            notes = "Status IN_USE→AVAILABLE; holder cleared"
        else:
            quantity_delta = usage.quantity
            notes = None
        self._revert_consumed(item, usage)
        self._item_repository.update(item)
        self._inventory_transaction_service.record(
            inventory_item=item,
            performed_by=current_user,
            transaction_type=InventoryTransactionType.CONSUME_UNDONE,
            ticket=ticket,
            quantity_delta=quantity_delta,
            notes=notes,
        )
        self._history_service.record(
            ticket.id,
            current_user,
            "inventory",
            None,
            f"Reverted consumption of {_describe(item, usage.quantity)}",
        )
        self._usage_repository.delete(usage)
        self._db.commit()

    def release_all_for_ticket(self, ticket: Ticket, current_user: User) -> None:
        """Called by TicketService.delete_ticket before removing a ticket,
        so deleting one never leaves inventory stuck RESERVED/IN_USE with
        no owning ticket. No role/ownership gate here - the caller (ticket
        deletion) has already been authorized at its own route.

        Does not write TicketHistory - the ticket and all its history rows
        are about to be deleted in this same request, so a history entry
        here would be pointless. Does still write InventoryTransaction:
        the item's own audit trail must not have a gap just because the
        ticket that caused this event no longer exists (see
        InventoryTransaction's ticket_id ON DELETE SET NULL and the
        ticket_number preserved in `notes` for exactly this reason).
        """
        usages = self._usage_repository.list_for_ticket(ticket.id)
        for usage in usages:
            item = usage.inventory_item
            is_serialized = item.tracking_type == InventoryTrackingType.SERIALIZED
            if usage.status == TicketInventoryUsageStatus.RESERVED:
                self._revert_reserved(item, usage)
                self._inventory_transaction_service.record(
                    inventory_item=item,
                    performed_by=current_user,
                    transaction_type=InventoryTransactionType.RELEASED,
                    ticket=ticket,
                    quantity_delta=-1 if is_serialized else -usage.quantity,
                    notes=f"Ticket {ticket.ticket_number} deleted; reservation released automatically.",
                )
            else:
                self._revert_consumed(item, usage)
                self._inventory_transaction_service.record(
                    inventory_item=item,
                    performed_by=current_user,
                    transaction_type=InventoryTransactionType.CONSUME_UNDONE,
                    ticket=ticket,
                    quantity_delta=usage.quantity if not is_serialized else None,
                    notes=f"Ticket {ticket.ticket_number} deleted; consumption reverted automatically.",
                )
            self._item_repository.update(item)
            self._usage_repository.delete(usage)
        if usages:
            self._db.commit()
