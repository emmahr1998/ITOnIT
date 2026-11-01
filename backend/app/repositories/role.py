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

    def get_by_names(self, names: tuple[str, ...]) -> list[Role]:
        """The roles matching ``names``, in the order given - used by GET
        /roles to list exactly the company-assignable roles (see
        app.core.roles.COMPANY_ROLE_NAMES) with their real ids."""
        by_name = {r.name: r for r in self.db.scalars(select(Role).where(Role.name.in_(names)))}
        return [by_name[name] for name in names if name in by_name]
