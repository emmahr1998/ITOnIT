from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import InventoryStatus, InventoryTrackingType
from app.models.inventory_category import InventoryCategory
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.user import User
from app.repositories.inventory_category import InventoryCategoryRepository
from app.repositories.inventory_item import InventoryItemRepository
from app.repositories.location import LocationRepository
from app.repositories.user import UserRepository
from app.schemas.inventory_item import InventoryItemCreate, InventoryItemUpdate

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

    No InventoryTransaction rows are written by this service - audit
    logging is Phase 10.4's job, not this one's (see the approved Phase
    10.2 scope).
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        item_repository: InventoryItemRepository | None = None,
        category_repository: InventoryCategoryRepository | None = None,
        location_repository: LocationRepository | None = None,
        user_repository: UserRepository | None = None,
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

    def create_item(self, payload: InventoryItemCreate) -> InventoryItem:
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
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the
            # asset_tag pre-check above and lose the race to the database's
            # filtered unique index, or trip a CHECK constraint this
            # service somehow didn't already catch.
            self._db.rollback()
            raise InventoryItemAssetTagConflictError from exc
        return item

    def update_item(self, item_id: int, payload: InventoryItemUpdate) -> InventoryItem:
        item = self.get_item(item_id)
        fields_set = payload.model_fields_set

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
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise InventoryItemAssetTagConflictError from exc
        return item
