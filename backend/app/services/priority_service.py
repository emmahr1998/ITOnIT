from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.priority import Priority
from app.repositories.priority import PriorityRepository
from app.schemas.priority import PriorityCreate, PriorityUpdate


class PriorityNotFoundError(Exception):
    """Raised when a priority id does not exist."""


class PriorityTitleConflictError(Exception):
    """Raised when a priority title already exists (case-insensitive)."""


class PriorityService:
    """Owns priority business rules: title uniqueness.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here. Same
    shape as DepartmentService/CategoryService.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        priority_repository: PriorityRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._priority_repository = (
            priority_repository
            if priority_repository is not None
            else PriorityRepository(db, company_id)
        )

    def list_priorities(self) -> list[Priority]:
        return self._priority_repository.get_all()

    def get_priority(self, priority_id: int) -> Priority:
        priority = self._priority_repository.get_by_id(priority_id)
        if priority is None:
            raise PriorityNotFoundError
        return priority

    def create_priority(self, payload: PriorityCreate) -> Priority:
        if self._priority_repository.get_by_title(payload.title) is not None:
            raise PriorityTitleConflictError

        priority = Priority(company_id=self._company_id, title=payload.title)
        try:
            self._priority_repository.create(priority)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise PriorityTitleConflictError from exc
        return priority

    def update_priority(self, priority_id: int, payload: PriorityUpdate) -> Priority:
        priority = self.get_priority(priority_id)

        if payload.title is not None:
            duplicate = self._priority_repository.get_by_title(payload.title)
            if duplicate is not None and duplicate.id != priority_id:
                raise PriorityTitleConflictError
            priority.title = payload.title

        try:
            self._priority_repository.update(priority)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise PriorityTitleConflictError from exc
        return priority
