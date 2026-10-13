from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.department import Department
from app.repositories.department import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentNotFoundError(Exception):
    """Raised when a department id does not exist."""


class DepartmentTitleConflictError(Exception):
    """Raised when a department title already exists (case-insensitive)."""


class DepartmentService:
    """Owns department business rules: title uniqueness.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here. Same
    shape as CategoryService; there is no delete-guard here because there
    is no DELETE endpoint for departments.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        department_repository: DepartmentRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._department_repository = (
            department_repository
            if department_repository is not None
            else DepartmentRepository(db, company_id)
        )

    def list_departments(self) -> list[Department]:
        return self._department_repository.get_all()

    def get_department(self, department_id: int) -> Department:
        department = self._department_repository.get_by_id(department_id)
        if department is None:
            raise DepartmentNotFoundError
        return department

    def create_department(self, payload: DepartmentCreate) -> Department:
        if self._department_repository.get_by_title(payload.title) is not None:
            raise DepartmentTitleConflictError

        department = Department(company_id=self._company_id, title=payload.title)
        try:
            self._department_repository.create(department)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DepartmentTitleConflictError from exc
        return department

    def update_department(self, department_id: int, payload: DepartmentUpdate) -> Department:
        department = self.get_department(department_id)

        if payload.title is not None:
            duplicate = self._department_repository.get_by_title(payload.title)
            if duplicate is not None and duplicate.id != department_id:
                raise DepartmentTitleConflictError
            department.title = payload.title

        try:
            self._department_repository.update(department)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DepartmentTitleConflictError from exc
        return department
