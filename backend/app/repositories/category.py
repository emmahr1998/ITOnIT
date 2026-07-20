from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.ticket import Ticket
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    """Category lookups needed for uniqueness checks and deletion safety."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Category)

    def get_by_name(self, name: str) -> Category | None:
        """Case-insensitive lookup, used to enforce unique category names."""
        return self.db.scalar(
            select(Category).where(func.lower(Category.name) == name.strip().lower())
        )

    def is_referenced_by_tickets(self, category_id: int) -> bool:
        """Whether any ticket currently references this category."""
        return (
            self.db.scalar(select(Ticket.id).where(Ticket.category_id == category_id).limit(1))
            is not None
        )
