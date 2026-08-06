from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.repositories.base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    """Location lookups needed for uniqueness checks."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Location)

    def get_by_title(self, title: str) -> Location | None:
        """Case-insensitive lookup, used to enforce unique location titles."""
        return self.db.scalar(
            select(Location).where(func.lower(Location.title) == title.strip().lower())
        )
