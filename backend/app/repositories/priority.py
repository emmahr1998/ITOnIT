from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.priority import Priority
from app.repositories.base import CompanyScopedRepository


class PriorityRepository(CompanyScopedRepository[Priority]):
    """Priority lookups needed for uniqueness checks. Company-scoped -
    see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Priority, company_id)

    def get_by_title(self, title: str) -> Priority | None:
        """Case-insensitive lookup, used to enforce unique priority titles
        within the caller's own company."""
        return self.db.scalar(
            select(Priority).where(
                func.lower(Priority.title) == title.strip().lower(),
                Priority.company_id == self.company_id,
            )
        )
