from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.repositories.base import CompanyScopedRepository


class DepartmentRepository(CompanyScopedRepository[Department]):
    """Department lookups needed for uniqueness checks. Company-scoped -
    see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Department, company_id)

    def get_by_title(self, title: str) -> Department | None:
        """Case-insensitive lookup, used to enforce unique department titles
        within the caller's own company."""
        return self.db.scalar(
            select(Department).where(
                func.lower(Department.title) == title.strip().lower(),
                Department.company_id == self.company_id,
            )
        )
