from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.repositories.base import CompanyScopedRepository


class LocationRepository(CompanyScopedRepository[Location]):
    """Location lookups needed for uniqueness checks. Company-scoped -
    see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Location, company_id)

    def get_by_title(self, title: str) -> Location | None:
        """Case-insensitive lookup, used to enforce unique location titles
        within the caller's own company."""
        return self.db.scalar(
            select(Location).where(
                func.lower(Location.title) == title.strip().lower(),
                Location.company_id == self.company_id,
            )
        )
