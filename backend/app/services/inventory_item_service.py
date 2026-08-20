from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import InventoryStatus, InventoryTrackingType, InventoryTransactionType
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.user import User
from app.repositories.inventory_category import InventoryCategoryRepository
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.location import LocationRepository
from app.repositories.user import UserRepository
from app.schemas.inventory_item import InventoryItemCreate, InventoryItemUpdate
from app.services.inventory_transaction_service import InventoryTransactionService

_BULK_ALLOWED_STATUSES = frozenset({InventoryStatus.AVAILABLE, InventoryStatus.RETIRED})
_SERIALIZED_ALLOWED_RESERVED = frozenset({0, 1})


class InventoryItemNotFoundError(Exception):
    """Raised when an inventory item id does not exist."""


class InventoryItemAssetTagConflictError(Exception):
    """Raised when an asset_tag already exists within the company
    (case-insensitive) - mirrors the filtered unique index from Phase 10.1,
    which only constrains non-null tags."""


class InventoryCategoryNotFoundError(Exception):
    """Raised when inventory_category_id does not reference a category in
    the caller's own company."""


class InventoryCategoryInactiveError(Exception):
    """Raised when inventory_category_id references a deactivated category -
    a deactivated category may not be newly assigned or reassigned, though
    items that already reference one are unaffected."""


class InventoryItemLocationNotFoundError(Exception):
    """Raised when current_location_id does not reference a location in the
    caller's own company."""


class InventoryItemHolderNotFoundError(Exception):
    """Raised when current_holder_user_id does not reference a user in the
    caller's own company."""


class InventoryItemValidationError(Exception):
    """Raised for any SERIALIZED/BULK business-rule violation or other
    cross-field validation failure - the service-level counterpart to the
    eight database CHECK constraints from Phase 10.1 (see
    InventoryItem's docstring for the exact list). This is the layer meant
    to produce a specific, friendly message; the CHECK constraints are the
    backstop for anything that reaches the database another way.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InventoryItemService:
    """Owns inventory item business rules: SERIALIZED vs. BULK validation,
    asset_tag uniqueness, and cross-company reference checks for
    inventory_category_id/current_location_id/current_holder_user_id.

    Also owns the transaction boundary for writes - repositories only
    flush, so commit()/rollback() happen here (same convention as every
    other service in this codebase).

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    It scopes every repository this service touches, including the
    internal category/location/user repositories - so a payload referencing
    another company's category/location/user can never resolve to a real
    row here (CompanyScopedRepository.get_by_id returns None for it, the
    same as a genuinely nonexistent id - see that class's docstring on why
    that's deliberate).

    Every create/update also records an InventoryTransaction row via
    InventoryTransactionService (Phase 12.1) - CREATED once per creation,
    then one row per field actually changed on update, using the
    dedicated STOCK_ADJUSTED/STATUS_CHANGED/HOLDER_CHANGED/
    LOCATION_CHANGED types for those specific fields and the generic
    EDITED type for everything else (see _record_update_transactions).
    This service is not ticket-related, so it never touches TicketHistory
    - only TicketInventoryService's reserve/release/consume/remove do
    that, since those are the actions that affect a ticket.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        item_repository: InventoryItemRepository | None = None,
        category_repository: InventoryCategoryRepository | None = None,
        location_repository: LocationRepository | None = None,
        user_repository: UserRepository | None = None,
        inventory_transaction_service: InventoryTransactionService | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._item_repository = (
            item_repository if item_repository is not None else InventoryItemRepository(db, company_id)
        )
        self._category_repository = (
            category_repository
            if category_repository is not None
            else InventoryCategoryRepository(db, company_id)
        )
        self._location_repository = (
            location_repository
            if location_repository is not None
            else LocationRepository(db, company_id)
        )
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db, company_id)
        )
        self._inventory_transaction_service = (
            inventory_transaction_service
            if inventory_transaction_service is not None
            else InventoryTransactionService(db, company_id)
        )

    # ---- reference lookups ------------------------------------------------

    def _get_active_category_or_raise(self, category_id: int) -> InventoryCategory:
        category = self._category_repository.get_by_id(category_id)
        if category is None:
            raise InventoryCategoryNotFoundError
        if not category.is_active:
            raise InventoryCategoryInactiveError
        return category

    def _get_location_or_raise(self, location_id: int) -> Location:
        location = self._location_repository.get_by_id(location_id)
        if location is None:
            raise InventoryItemLocationNotFoundError
        return location

    def _get_holder_or_raise(self, user_id: int) -> User:
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise InventoryItemHolderNotFoundError
        return user

    # ---- business-rule validation -----------------------------------------

    @staticmethod
    def _validate_business_rules(item: InventoryItem) -> None:
        """The service-level counterpart to the eight CHECK constraints,
        run against the fully assembled item (after every field from the
        request has already been applied) - see InventoryItem's docstring
        for the exact list this mirrors. Also covers purchase_cost/date
        sensibility, which isn't a CHECK constraint at all.
        """
        if (
            item.purchase_date is not None
            and item.warranty_expiration is not None
            and item.warranty_expiration < item.purchase_date
        ):
            raise InventoryItemValidationError(
                "warranty_expiration cannot be before purchase_date"
            )

        if item.stock_quantity < 0:
            raise InventoryItemValidationError("stock_quantity must be 0 or greater")
        if item.reserved_quantity < 0 or item.reserved_quantity > item.stock_quantity:
            raise InventoryItemValidationError(
                "reserved_quantity must be between 0 and stock_quantity"
            )

        if item.tracking_type == InventoryTrackingType.SERIALIZED:
            if not item.asset_tag:
                raise InventoryItemValidationError("asset_tag is required for serialized items")
            if item.stock_quantity != 1:
                raise InventoryItemValidationError(
                    "stock_quantity must be 1 for serialized items"
                )
            if item.reserved_quantity not in _SERIALIZED_ALLOWED_RESERVED:
                raise InventoryItemValidationError(
                    "reserved_quantity must be 0 or 1 for serialized items"
                )
        else:  # BULK
            if item.status not in _BULK_ALLOWED_STATUSES:
                raise InventoryItemValidationError(
                    "status must be AVAILABLE or RETIRED for bulk items"
                )
            if item.current_holder_user_id is not None:
                raise InventoryItemValidationError(
                    "current_holder_user_id must be null for bulk items"
                )
            if item.condition is not None:
                raise InventoryItemValidationError("condition must be null for bulk items")
            if item.reserved_quantity != 0:
                raise InventoryItemValidationError(
                    "reserved_quantity must be 0 - reservations are not supported yet"
                )

    # ---- reads -----------------------------------------------------------

    def list_items(
        self,
        *,
        inventory_category_id: int | None = None,
        tracking_type: InventoryTrackingType | None = None,
        status: InventoryStatus | None = None,
        condition=None,
        current_location_id: int | None = None,
        current_holder_user_id: int | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        search: str | None = None,
        low_stock: bool | None = None,
        warranty_expiring_days: int | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InventoryItem], int]:
        filters = dict(
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
        items = self._item_repository.get_with_filters(
            **filters, sort_by=sort_by, sort_dir=sort_dir, skip=skip, limit=limit
        )
        total = self._item_repository.count_with_filters(**filters)
        return items, total

    def get_item(self, item_id: int) -> InventoryItem:
        item = self._item_repository.get_by_id(item_id)
        if item is None:
            raise InventoryItemNotFoundError
        return item

    # ---- writes ------------------------------------------------------------

    def create_item(self, payload: InventoryItemCreate, current_user: User) -> InventoryItem:
        category = self._get_active_category_or_raise(payload.inventory_category_id)
        location = (
            self._get_location_or_raise(payload.current_location_id)
            if payload.current_location_id is not None
            else None
        )
        holder = (
            self._get_holder_or_raise(payload.current_holder_user_id)
            if payload.current_holder_user_id is not None
            else None
        )

        if payload.asset_tag is not None:
            if self._item_repository.get_by_asset_tag(payload.asset_tag) is not None:
                raise InventoryItemAssetTagConflictError

        if payload.stock_quantity is not None:
            stock_quantity = payload.stock_quantity
        elif payload.tracking_type == InventoryTrackingType.SERIALIZED:
            stock_quantity = 1
        else:
            raise InventoryItemValidationError("stock_quantity is required for bulk items")

        item = InventoryItem(
            company_id=self._company_id,
            inventory_category_id=category.id,
            current_location_id=location.id if location is not None else None,
            current_holder_user_id=holder.id if holder is not None else None,
            asset_tag=payload.asset_tag,
            name=payload.name,
            manufacturer=payload.manufacturer,
            model=payload.model,
            serial_number=payload.serial_number,
            tracking_type=payload.tracking_type,
            status=payload.status,
            condition=payload.condition,
            stock_quantity=stock_quantity,
            reserved_quantity=0,
            minimum_stock=payload.minimum_stock,
            purchase_date=payload.purchase_date,
            warranty_expiration=payload.warranty_expiration,
            supplier=payload.supplier,
            purchase_cost=payload.purchase_cost,
            invoice_number=payload.invoice_number,
            image_path=payload.image_path,
            notes=payload.notes,
        )
        item.inventory_category = category
        item.current_location = location
        item.current_holder = holder

        self._validate_business_rules(item)

        try:
            self._item_repository.create(item)
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.CREATED,
                quantity_delta=item.stock_quantity,
                notes=(
                    f"Created as {item.tracking_type.value}"
                    + (f", asset tag {item.asset_tag}" if item.asset_tag else "")
                ),
            )
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the
            # asset_tag pre-check above and lose the race to the database's
            # filtered unique index, or trip a CHECK constraint this
            # service somehow didn't already catch.
            self._db.rollback()
            raise InventoryItemAssetTagConflictError from exc
        return item

    def update_item(
        self, item_id: int, payload: InventoryItemUpdate, current_user: User
    ) -> InventoryItem:
        item = self.get_item(item_id)
        fields_set = payload.model_fields_set

        # Snapshot every field an InventoryTransaction might need a
        # before/after comparison for, taken before any mutation below -
        # see _record_update_transactions, called after the mutations and
        # validation succeed.
        old_category_name = item.inventory_category.name
        old_location = item.current_location
        old_holder = item.current_holder
        old_status = item.status
        old_stock_quantity = item.stock_quantity
        old_simple_values = {
            "name": item.name,
            "manufacturer": item.manufacturer,
            "model": item.model,
            "serial_number": item.serial_number,
            "asset_tag": item.asset_tag,
            "condition": item.condition,
            "minimum_stock": item.minimum_stock,
            "purchase_date": item.purchase_date,
            "warranty_expiration": item.warranty_expiration,
            "supplier": item.supplier,
            "purchase_cost": item.purchase_cost,
            "invoice_number": item.invoice_number,
            "image_path": item.image_path,
            "notes": item.notes,
        }

        if "inventory_category_id" in fields_set and payload.inventory_category_id is not None:
            category = self._get_active_category_or_raise(payload.inventory_category_id)
            item.inventory_category_id = category.id
            item.inventory_category = category

        if "current_location_id" in fields_set:
            location = (
                self._get_location_or_raise(payload.current_location_id)
                if payload.current_location_id is not None
                else None
            )
            item.current_location_id = payload.current_location_id
            item.current_location = location

        if "current_holder_user_id" in fields_set:
            holder = (
                self._get_holder_or_raise(payload.current_holder_user_id)
                if payload.current_holder_user_id is not None
                else None
            )
            item.current_holder_user_id = payload.current_holder_user_id
            item.current_holder = holder

        if "asset_tag" in fields_set:
            if payload.asset_tag is not None:
                duplicate = self._item_repository.get_by_asset_tag(payload.asset_tag)
                if duplicate is not None and duplicate.id != item.id:
                    raise InventoryItemAssetTagConflictError
            item.asset_tag = payload.asset_tag

        if "name" in fields_set and payload.name is not None:
            item.name = payload.name
        if "manufacturer" in fields_set:
            item.manufacturer = payload.manufacturer
        if "model" in fields_set:
            item.model = payload.model
        if "serial_number" in fields_set:
            item.serial_number = payload.serial_number
        if "status" in fields_set and payload.status is not None:
            item.status = payload.status
        if "condition" in fields_set:
            item.condition = payload.condition
        if "stock_quantity" in fields_set and payload.stock_quantity is not None:
            item.stock_quantity = payload.stock_quantity
        if "minimum_stock" in fields_set:
            item.minimum_stock = payload.minimum_stock
        if "purchase_date" in fields_set:
            item.purchase_date = payload.purchase_date
        if "warranty_expiration" in fields_set:
            item.warranty_expiration = payload.warranty_expiration
        if "supplier" in fields_set:
            item.supplier = payload.supplier
        if "purchase_cost" in fields_set:
            item.purchase_cost = payload.purchase_cost
        if "invoice_number" in fields_set:
            item.invoice_number = payload.invoice_number
        if "image_path" in fields_set:
            item.image_path = payload.image_path
        if "notes" in fields_set:
            item.notes = payload.notes

        self._validate_business_rules(item)

        try:
            self._item_repository.update(item)
            self._record_update_transactions(
                item,
                current_user,
                old_category_name=old_category_name,
                old_location=old_location,
                old_holder=old_holder,
                old_status=old_status,
                old_stock_quantity=old_stock_quantity,
                old_simple_values=old_simple_values,
            )
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise InventoryItemAssetTagConflictError from exc
        return item

    def _record_update_transactions(
        self,
        item: InventoryItem,
        current_user: User,
        *,
        old_category_name: str,
        old_location: Location | None,
        old_holder: User | None,
        old_status: InventoryStatus,
        old_stock_quantity: int,
        old_simple_values: dict[str, object],
    ) -> None:
        """One InventoryTransaction row per field actually changed by
        update_item - never a row for a field that was in the payload but
        didn't change value. status/current_holder_user_id/
        current_location_id/stock_quantity get their own dedicated
        transaction types (matching the ones reserve/release/consume/
        remove use for the same fields, so "every status change" is
        queryable as one coherent set regardless of what triggered it);
        every other changed field falls back to the generic EDITED type.
        """
        if item.inventory_category.name != old_category_name:
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.EDITED,
                field_name="inventory_category_id",
                old_value=old_category_name,
                new_value=item.inventory_category.name,
            )

        new_location_title = item.current_location.title if item.current_location else None
        old_location_title = old_location.title if old_location else None
        if new_location_title != old_location_title:
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.LOCATION_CHANGED,
                field_name="current_location_id",
                old_value=old_location_title,
                new_value=new_location_title,
            )

        new_holder_name = (
            f"{item.current_holder.first_name} {item.current_holder.last_name}"
            if item.current_holder
            else None
        )
        old_holder_name = (
            f"{old_holder.first_name} {old_holder.last_name}" if old_holder else None
        )
        if new_holder_name != old_holder_name:
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.HOLDER_CHANGED,
                field_name="current_holder_user_id",
                old_value=old_holder_name,
                new_value=new_holder_name,
            )

        if item.status != old_status:
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.STATUS_CHANGED,
                field_name="status",
                old_value=old_status.value,
                new_value=item.status.value,
            )

        if item.stock_quantity != old_stock_quantity:
            self._inventory_transaction_service.record(
                inventory_item=item,
                performed_by=current_user,
                transaction_type=InventoryTransactionType.STOCK_ADJUSTED,
                quantity_delta=item.stock_quantity - old_stock_quantity,
                field_name="stock_quantity",
                old_value=str(old_stock_quantity),
                new_value=str(item.stock_quantity),
            )

        new_simple_values = {
            "name": item.name,
            "manufacturer": item.manufacturer,
            "model": item.model,
            "serial_number": item.serial_number,
            "asset_tag": item.asset_tag,
            "condition": item.condition,
            "minimum_stock": item.minimum_stock,
            "purchase_date": item.purchase_date,
            "warranty_expiration": item.warranty_expiration,
            "supplier": item.supplier,
            "purchase_cost": item.purchase_cost,
            "invoice_number": item.invoice_number,
            "image_path": item.image_path,
            "notes": item.notes,
        }
        for field_name, new_value in new_simple_values.items():
            old_value = old_simple_values[field_name]
            if new_value != old_value:
                self._inventory_transaction_service.record(
                    inventory_item=item,
                    performed_by=current_user,
                    transaction_type=InventoryTransactionType.EDITED,
                    field_name=field_name,
                    old_value=self._stringify(old_value),
                    new_value=self._stringify(new_value),
                )

    @staticmethod
    def _stringify(value: object) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):  # enum member, e.g. InventoryCondition
            return value.value
        return str(value)
