from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Role lookups needed for authentication and initial-data seeding."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Role)

    def get_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))
