from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.priority import Priority
from app.repositories.base import BaseRepository


class PriorityRepository(BaseRepository[Priority]):
    """Priority lookups needed for uniqueness checks."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Priority)

    def get_by_title(self, title: str) -> Priority | None:
        """Case-insensitive lookup, used to enforce unique priority titles."""
        return self.db.scalar(
            select(Priority).where(func.lower(Priority.title) == title.strip().lower())
        )
