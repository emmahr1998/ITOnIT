from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import InventoryTransactionType
from app.models.inventory_transaction import InventoryTransaction
from app.repositories.base import CompanyScopedRepository

_EAGER_OPTIONS = (
    selectinload(InventoryTransaction.inventory_item),
    selectinload(InventoryTransaction.ticket),
    selectinload(InventoryTransaction.performed_by),
)


class InventoryTransactionRepository(CompanyScopedRepository[InventoryTransaction]):
    """InventoryTransaction persistence: per-item and company-wide listing.
    Company-scoped - see CompanyScopedRepository. Every custom query below
    adds its own `company_id == self.company_id` predicate, per that base
    class's documented requirement.

    Append-only, enforced structurally rather than by convention alone:
    BaseRepository (like every repository in this codebase) provides
    update()/delete() by inheritance, so this class overrides both to
    raise instead - there is no way to mutate or remove a row once
    written, even by a caller that bypasses InventoryTransactionService.
    Only create() (inherited, unmodified) and reads are usable.
    """

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, InventoryTransaction, company_id)

    def update(self, obj: InventoryTransaction) -> InventoryTransaction:
        raise NotImplementedError("InventoryTransaction is append-only - rows are never updated")

    def delete(self, obj: InventoryTransaction) -> None:
        raise NotImplementedError("InventoryTransaction is append-only - rows are never deleted")

    def _filtered_statement(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type: InventoryTransactionType | None = None,
        performed_by_user_id: int | None = None,
    ):
        stmt = (
            select(InventoryTransaction)
            .where(InventoryTransaction.company_id == self.company_id)
            .options(*_EAGER_OPTIONS)
        )
        if inventory_item_id is not None:
            stmt = stmt.where(InventoryTransaction.inventory_item_id == inventory_item_id)
        if ticket_id is not None:
            stmt = stmt.where(InventoryTransaction.ticket_id == ticket_id)
        if transaction_type is not None:
            stmt = stmt.where(InventoryTransaction.transaction_type == transaction_type)
        if performed_by_user_id is not None:
            stmt = stmt.where(InventoryTransaction.performed_by_user_id == performed_by_user_id)
        return stmt

    def list_for_item(
        self, inventory_item_id: int, *, skip: int = 0, limit: int = 100
    ) -> list[InventoryTransaction]:
        stmt = (
            self._filtered_statement(inventory_item_id=inventory_item_id)
            .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def count_for_item(self, inventory_item_id: int) -> int:
        stmt = self._filtered_statement(inventory_item_id=inventory_item_id)
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    def list_company_transactions(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type: InventoryTransactionType | None = None,
        performed_by_user_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[InventoryTransaction]:
        stmt = (
            self._filtered_statement(
                inventory_item_id=inventory_item_id,
                ticket_id=ticket_id,
                transaction_type=transaction_type,
                performed_by_user_id=performed_by_user_id,
            )
            .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def count_company_transactions(
        self,
        *,
        inventory_item_id: int | None = None,
        ticket_id: int | None = None,
        transaction_type: InventoryTransactionType | None = None,
        performed_by_user_id: int | None = None,
    ) -> int:
        stmt = self._filtered_statement(
            inventory_item_id=inventory_item_id,
            ticket_id=ticket_id,
            transaction_type=transaction_type,
            performed_by_user_id=performed_by_user_id,
        )
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
