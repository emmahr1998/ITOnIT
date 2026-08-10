from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import InventoryCondition, InventoryStatus, InventoryTrackingType
from app.models.inventory_item import InventoryItem
from app.repositories.base import CompanyScopedRepository

_EAGER_OPTIONS = (
    selectinload(InventoryItem.inventory_category),
    selectinload(InventoryItem.current_location),
    selectinload(InventoryItem.current_holder),
)

_SORTABLE_COLUMNS = {
    "created_at": InventoryItem.created_at,
    "updated_at": InventoryItem.updated_at,
    "name": InventoryItem.name,
    "purchase_date": InventoryItem.purchase_date,
    "warranty_expiration": InventoryItem.warranty_expiration,
}


class InventoryItemRepository(CompanyScopedRepository[InventoryItem]):
    """InventoryItem persistence: filtered/searched/sorted/paginated
    listing plus asset_tag lookups. Company-scoped - see
    CompanyScopedRepository. Every custom query below adds its own
    `company_id == self.company_id` predicate, per that base class's
    documented requirement.
    """

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, InventoryItem, company_id)

    def get_by_id(self, id_: int) -> InventoryItem | None:
        """Overrides CompanyScopedRepository.get_by_id to eager-load the
        relationships InventoryItemResponse needs, avoiding an N+1 query."""
        return self.db.scalar(
            select(InventoryItem)
            .where(InventoryItem.id == id_, InventoryItem.company_id == self.company_id)
            .options(*_EAGER_OPTIONS)
        )

    def get_by_asset_tag(self, asset_tag: str) -> InventoryItem | None:
        """Case-insensitive lookup, used to enforce the filtered unique
        index's intent (unique per company among non-null tags) with a
        friendly pre-check before the database's own backstop."""
        return self.db.scalar(
            select(InventoryItem).where(
                func.lower(InventoryItem.asset_tag) == asset_tag.strip().lower(),
                InventoryItem.company_id == self.company_id,
            )
        )

    def _filtered_statement(
        self,
        *,
        inventory_category_id: int | None = None,
        tracking_type: InventoryTrackingType | None = None,
        status: InventoryStatus | None = None,
        condition: InventoryCondition | None = None,
        current_location_id: int | None = None,
        current_holder_user_id: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        search: str | None = None,
        low_stock: bool | None = None,
        warranty_expiring_days: int | None = None,
    ):
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.company_id == self.company_id)
            .options(*_EAGER_OPTIONS)
        )
        if inventory_category_id is not None:
            stmt = stmt.where(InventoryItem.inventory_category_id == inventory_category_id)
        if tracking_type is not None:
            stmt = stmt.where(InventoryItem.tracking_type == tracking_type)
        if status is not None:
            stmt = stmt.where(InventoryItem.status == status)
        if condition is not None:
            stmt = stmt.where(InventoryItem.condition == condition)
        if current_location_id is not None:
            stmt = stmt.where(InventoryItem.current_location_id == current_location_id)
        if current_holder_user_id is not None:
            stmt = stmt.where(InventoryItem.current_holder_user_id == current_holder_user_id)
        if manufacturer:
            stmt = stmt.where(func.lower(InventoryItem.manufacturer) == manufacturer.strip().lower())
        if model:
            stmt = stmt.where(func.lower(InventoryItem.model) == model.strip().lower())
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(InventoryItem.name).like(pattern),
                    func.lower(InventoryItem.asset_tag).like(pattern),
                    func.lower(InventoryItem.serial_number).like(pattern),
                    func.lower(InventoryItem.manufacturer).like(pattern),
                    func.lower(InventoryItem.model).like(pattern),
                    func.lower(InventoryItem.supplier).like(pattern),
                    func.lower(InventoryItem.invoice_number).like(pattern),
                )
            )
        if low_stock:
            # BULK only - a SERIALIZED row's stock_quantity is always 1 and
            # has no meaningful "minimum" concept.
            stmt = stmt.where(
                InventoryItem.tracking_type == InventoryTrackingType.BULK,
                InventoryItem.minimum_stock.is_not(None),
                (InventoryItem.stock_quantity - InventoryItem.reserved_quantity)
                <= InventoryItem.minimum_stock,
            )
        if warranty_expiring_days is not None:
            today = datetime.now(timezone.utc).date()
            horizon = today + timedelta(days=warranty_expiring_days)
            stmt = stmt.where(
                InventoryItem.warranty_expiration.is_not(None),
                InventoryItem.warranty_expiration >= today,
                InventoryItem.warranty_expiration <= horizon,
            )
        return stmt

    def get_with_filters(
        self,
        *,
        inventory_category_id: int | None = None,
        tracking_type: InventoryTrackingType | None = None,
        status: InventoryStatus | None = None,
        condition: InventoryCondition | None = None,
        current_location_id: int | None = None,
        current_holder_user_id: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        search: str | None = None,
        low_stock: bool | None = None,
        warranty_expiring_days: int | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int | None = None,
        limit: int | None = None,
    ) -> list[InventoryItem]:
        stmt = self._filtered_statement(
            inventory_category_id=inventory_category_id,
            tracking_type=tracking_type,
            status=status,
            condition=condition,
            current_location_id=current_location_id,
            current_holder_user_id=current_holder_user_id,
            manufacturer=manufacturer,
            model=model,
            search=search,
            low_stock=low_stock,
            warranty_expiring_days=warranty_expiring_days,
        )
        # Allow-listed lookup, never a client-supplied column name reaching
        # SQL directly - an unrecognized sort_by silently falls back to
        # created_at, matching TicketRepository.get_with_filters.
        sort_column = _SORTABLE_COLUMNS.get(sort_by, InventoryItem.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

        if skip is not None:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_with_filters(
        self,
        *,
        inventory_category_id: int | None = None,
        tracking_type: InventoryTrackingType | None = None,
        status: InventoryStatus | None = None,
        condition: InventoryCondition | None = None,
        current_location_id: int | None = None,
        current_holder_user_id: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        search: str | None = None,
        low_stock: bool | None = None,
        warranty_expiring_days: int | None = None,
    ) -> int:
        stmt = self._filtered_statement(
            inventory_category_id=inventory_category_id,
            tracking_type=tracking_type,
            status=status,
            condition=condition,
            current_location_id=current_location_id,
            current_holder_user_id=current_holder_user_id,
            manufacturer=manufacturer,
            model=model,
            search=search,
            low_stock=low_stock,
            warranty_expiring_days=warranty_expiring_days,
        )
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
