from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryNotFoundError(Exception):
    """Raised when a category id does not exist."""


class CategoryNameConflictError(Exception):
    """Raised when a category name already exists (case-insensitive)."""


class CategoryInUseError(Exception):
    """Raised when attempting to delete a category still referenced by tickets."""


class CategoryService:
    """Owns category business rules: name uniqueness and deletion safety.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here.
    """

    def __init__(
        self, db: Session, category_repository: CategoryRepository | None = None
    ) -> None:
        self._db = db
        self._category_repository = (
            category_repository if category_repository is not None else CategoryRepository(db)
        )

    def list_categories(self) -> list[Category]:
        return self._category_repository.get_all()

    def get_category(self, category_id: int) -> Category:
        category = self._category_repository.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundError
        return category

    def create_category(self, payload: CategoryCreate) -> Category:
        if self._category_repository.get_by_name(payload.name) is not None:
            raise CategoryNameConflictError

        category = Category(name=payload.name, description=payload.description)
        try:
            self._category_repository.create(category)
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the check
            # above and lose the race to the database's unique constraint.
            self._db.rollback()
            raise CategoryNameConflictError from exc
        return category

    def update_category(self, category_id: int, payload: CategoryUpdate) -> Category:
        category = self.get_category(category_id)

        duplicate = self._category_repository.get_by_name(payload.name)
        if duplicate is not None and duplicate.id != category_id:
            raise CategoryNameConflictError

        category.name = payload.name
        category.description = payload.description
        try:
            self._category_repository.update(category)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise CategoryNameConflictError from exc
        return category

    def delete_category(self, category_id: int) -> None:
        category = self.get_category(category_id)
        if self._category_repository.is_referenced_by_tickets(category_id):
            raise CategoryInUseError
        try:
            self._category_repository.delete(category)
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a ticket could start referencing this
            # category after the pre-check above but before this delete
            # reaches the database (the FK constraint catches it either way).
            self._db.rollback()
            raise CategoryInUseError from exc
