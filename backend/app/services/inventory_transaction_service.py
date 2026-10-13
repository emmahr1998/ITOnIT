from sqlalchemy.orm import Session

from app.models.enums import InventoryTransactionType
from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.ticket import Ticket
from app.models.user import User
from app.repositories.inventory_transaction import InventoryTransactionRepository

_MAX_VALUE_LENGTH = 255  # matches InventoryTransaction.old_value/new_value column width


class InventoryTransactionService:
    """Owns InventoryTransaction writes - the one place every inventory-
    affecting event records an audit entry, so this logic is never
    duplicated per call site (same role as HistoryService for tickets).

    Deliberately does not commit: recording a transaction is always one
    step inside a larger operation (creating/editing an item, reserving/
    releasing/consuming against a ticket...) owned by whichever service
    orchestrates that operation. This only flushes (via
    InventoryTransactionRepository/BaseRepository), matching the project
    convention that repositories persist and the orchestrating service
    owns the transaction boundary - so a flush failure here (or anywhere
    else in that same unit of work) rolls back the whole operation,
    including the inventory mutation that triggered it. See
    InventoryTransaction's own docstring for the append-only guarantee
    this and InventoryTransactionRepository together provide: this class
    has no update()/delete() of its own, InventoryTransactionRepository's
    inherited update()/delete() are overridden to raise, and no route
    exposes either.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client
    input - it is denormalized from the parent item, same as on the
    model itself.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        transaction_repository: InventoryTransactionRepository | None = None,
    ) -> None:
        self._company_id = company_id
        self._transaction_repository = (
            transaction_repository
            if transaction_repository is not None
            else InventoryTransactionRepository(db, company_id)
        )

    def record(
        self,
        *,
        inventory_item: InventoryItem,
        performed_by: User,
        transaction_type: InventoryTransactionType,
        ticket: Ticket | None = None,
        quantity_delta: int | None = None,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        notes: str | None = None,
    ) -> InventoryTransaction:
        entry = InventoryTransaction(
            company_id=self._company_id,
            inventory_item_id=inventory_item.id,
            ticket_id=ticket.id if ticket is not None else None,
            performed_by_user_id=performed_by.id,
            transaction_type=transaction_type,
            quantity_delta=quantity_delta,
            field_name=field_name,
            old_value=self._truncate(old_value),
            new_value=self._truncate(new_value),
            notes=notes,
        )
        # Set every relationship directly (not just the FK) - same
        # rationale as HistoryService.record: avoids depending on
        # lazy-load timing (this entry is a transient object, never
        # flushed through a real session in tests, so lazy-loading isn't
        # even possible there), and InventoryTransactionResponse needs
        # inventory_item/ticket/performed_by all populated to serialize.
        entry.inventory_item = inventory_item
        entry.ticket = ticket
        entry.performed_by = performed_by
        return self._transaction_repository.create(entry)

    def list_for_item(
        self, inventory_item_id: int, *, skip: int = 0, limit: int = 100
    ) -> tuple[list[InventoryTransaction], int]:
        transactions = self._transaction_repository.list_for_item(
            inventory_item_id, skip=skip, limit=limit
        )
        total = self._transaction_repository.count_for_item(inventory_item_id)
        return transactions, total

    def list_company_transactions(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type: InventoryTransactionType | None = None,
        performed_by_user_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryTransaction], int]:
        filters = dict(
            inventory_item_id=inventory_item_id,
            ticket_id=ticket_id,
            transaction_type=transaction_type,
            performed_by_user_id=performed_by_user_id,
        )
        transactions = self._transaction_repository.list_company_transactions(
            **filters, skip=skip, limit=limit
        )
        total = self._transaction_repository.count_company_transactions(**filters)
        return transactions, total

    @staticmethod
    def _truncate(value: str | None) -> str | None:
        if value is None:
            return None
        return value[:_MAX_VALUE_LENGTH]
