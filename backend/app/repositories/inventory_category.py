from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory_category import InventoryCategory
from app.repositories.base import CompanyScopedRepository


class InventoryCategoryRepository(CompanyScopedRepository[InventoryCategory]):
    """InventoryCategory lookups needed for uniqueness checks and starter-data
    seeding. Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, InventoryCategory, company_id)

    def get_by_name(self, name: str) -> InventoryCategory | None:
        """Case-insensitive lookup, used to enforce unique inventory
        category names within the caller's own company."""
        return self.db.scalar(
            select(InventoryCategory).where(
                func.lower(InventoryCategory.name) == name.strip().lower(),
                InventoryCategory.company_id == self.company_id,
            )
        )

    def count_all(self) -> int:
        """Used by the idempotent starter-data backfill to detect a company
        that already has inventory categories (skip) vs. one that has none
        yet (seed)."""
        return len(self.get_all())
