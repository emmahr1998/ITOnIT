from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.inventory_category import InventoryCategory
from app.repositories.inventory_category import InventoryCategoryRepository
from app.schemas.inventory_category import InventoryCategoryCreate, InventoryCategoryUpdate


class InventoryCategoryNotFoundError(Exception):
    """Raised when an inventory category id does not exist."""


class InventoryCategoryNameConflictError(Exception):
    """Raised when an inventory category name already exists (case-insensitive)."""


class InventoryCategoryService:
    """Owns inventory category business rules: name uniqueness.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here. Same
    shape as LocationService: there is no delete method because categories
    are deactivated (is_active=False) instead of deleted, so an inventory
    item already referencing one keeps a valid reference.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        inventory_category_repository: InventoryCategoryRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._inventory_category_repository = (
            inventory_category_repository
            if inventory_category_repository is not None
            else InventoryCategoryRepository(db, company_id)
        )

    def list_categories(self) -> list[InventoryCategory]:
        return self._inventory_category_repository.get_all()

    def get_category(self, category_id: int) -> InventoryCategory:
        category = self._inventory_category_repository.get_by_id(category_id)
        if category is None:
            raise InventoryCategoryNotFoundError
        return category

    def create_category(self, payload: InventoryCategoryCreate) -> InventoryCategory:
        if self._inventory_category_repository.get_by_name(payload.name) is not None:
            raise InventoryCategoryNameConflictError

        category = InventoryCategory(
            company_id=self._company_id, name=payload.name, is_active=True
        )
        try:
            self._inventory_category_repository.create(category)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise InventoryCategoryNameConflictError from exc
        return category

    def update_category(
        self, category_id: int, payload: InventoryCategoryUpdate
    ) -> InventoryCategory:
        category = self.get_category(category_id)

        if payload.name is not None:
            duplicate = self._inventory_category_repository.get_by_name(payload.name)
            if duplicate is not None and duplicate.id != category_id:
                raise InventoryCategoryNameConflictError
            category.name = payload.name

        if payload.is_active is not None:
            category.is_active = payload.is_active

        try:
            self._inventory_category_repository.update(category)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise InventoryCategoryNameConflictError from exc
        return category
