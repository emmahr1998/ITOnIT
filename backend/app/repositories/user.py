from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User lookups needed for authentication."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def get_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup, since email is the login identifier."""
        return self.db.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )
