from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.repositories.base import BaseRepository

_EAGER_OPTIONS = (selectinload(User.role), selectinload(User.department))


class UserRepository(BaseRepository[User]):
    """User lookups needed for authentication and user management."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def get_by_id(self, id_: int) -> User | None:
        """Overrides BaseRepository.get_by_id to eager-load role/department,
        which every UserResponse needs."""
        return self.db.scalar(select(User).where(User.id == id_).options(*_EAGER_OPTIONS))

    def get_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup, since email is a login identifier."""
        return self.db.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )

    def get_by_username(self, username: str) -> User | None:
        """Case-insensitive lookup by username."""
        return self.db.scalar(
            select(User).where(func.lower(User.username) == username.strip().lower())
        )

    def get_by_username_or_email(self, identifier: str) -> User | None:
        """Case-insensitive lookup matching either username or email.

        Lets ``username`` remain the one documented login field while still
        accepting an email address, without adding a second login field.
        """
        normalized = identifier.strip().lower()
        return self.db.scalar(
            select(User).where(
                or_(
                    func.lower(User.username) == normalized,
                    func.lower(User.email) == normalized,
                )
            )
        )

    def _filtered_statement(
        self,
        *,
        role_id: int | None,
        department_id: int | None,
        is_active: bool | None,
        search: str | None,
    ):
        stmt = select(User).options(*_EAGER_OPTIONS)
        if role_id is not None:
            stmt = stmt.where(User.role_id == role_id)
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.username).like(pattern),
                    func.lower(User.first_name).like(pattern),
                    func.lower(User.last_name).like(pattern),
                    func.lower(User.email).like(pattern),
                )
            )
        return stmt

    def get_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """One filter method covers every caller of GET /users: role,
        department, active-status, and a free-text search across name,
        username, and email, all paginated with skip/limit."""
        stmt = self._filtered_statement(
            role_id=role_id, department_id=department_id, is_active=is_active, search=search
        )
        stmt = stmt.order_by(User.id).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def count_with_filters(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> int:
        """Total matching rows for the same filters as get_with_filters,
        ignoring skip/limit - used to report pagination totals."""
        stmt = self._filtered_statement(
            role_id=role_id, department_id=department_id, is_active=is_active, search=search
        )
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
