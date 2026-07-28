from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import Department
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    """Department lookups needed for uniqueness checks."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Department)

    def get_by_title(self, title: str) -> Department | None:
        """Case-insensitive lookup, used to enforce unique department titles."""
        return self.db.scalar(
            select(Department).where(func.lower(Department.title) == title.strip().lower())
        )
