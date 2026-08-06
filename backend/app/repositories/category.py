from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.ticket import Ticket
from app.repositories.base import CompanyScopedRepository


class CategoryRepository(CompanyScopedRepository[Category]):
    """Category lookups needed for uniqueness checks and deletion safety.
    Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Category, company_id)

    def get_by_name(self, name: str) -> Category | None:
        """Case-insensitive lookup, used to enforce unique category names
        within the caller's own company."""
        return self.db.scalar(
            select(Category).where(
                func.lower(Category.name) == name.strip().lower(),
                Category.company_id == self.company_id,
            )
        )

    def is_referenced_by_tickets(self, category_id: int) -> bool:
        """Whether any ticket currently references this category.

        The company_id filter here is belt-and-suspenders, not
        load-bearing: category_id alone already identifies a row confined
        to one company, so no other company's ticket could reference it in
        the first place. Included anyway so every query in this class
        follows the same scoped pattern without exception.
        """
        return (
            self.db.scalar(
                select(Ticket.id)
                .where(Ticket.category_id == category_id, Ticket.company_id == self.company_id)
                .limit(1)
            )
            is not None
        )
