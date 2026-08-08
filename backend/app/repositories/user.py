from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User
from app.repositories.base import BaseRepository

_EAGER_OPTIONS = (
    selectinload(User.role),
    selectinload(User.department),
    selectinload(User.company),
)


class UserRepository(BaseRepository[User]):
    """User lookups needed for authentication and user management.

    Deliberately NOT built on CompanyScopedRepository. Two different auth
    call sites need two different kinds of scoping, neither of which fits
    "always scoped at construction time":
      - get_current_user (via get_by_id) must resolve "who is this JWT for"
        with no company known yet at all - the company is derived *from*
        the user this call finds, not the other way around. Constructed
        with company_id=None (unscoped).
      - AuthService.login (via get_by_username_or_email) resolves the
        company first, from the request's company_code, then looks up the
        user *within* that company - but the company differs on every call,
        so it's passed as an explicit method parameter rather than fixed at
        construction time.
    Every user-management call site (UserService, via get_user_service)
    fits the normal pattern: company known once per request, fixed at
    construction, scoping every method below via self.company_id/_scope().
    """

    def __init__(self, db: Session, company_id: int | None = None) -> None:
        super().__init__(db, User)
        self.company_id = company_id

    def _scope(self, stmt):
        if self.company_id is not None:
            stmt = stmt.where(User.company_id == self.company_id)
        return stmt

    def get_by_id(self, id_: int) -> User | None:
        """Overrides BaseRepository.get_by_id to eager-load role/department/
        company - role/department for UserResponse, company so
        get_current_active_user can check current_user.company.is_active on
        every request without a lazy-load - and to apply company scoping
        only when this instance was constructed with one (see class
        docstring)."""
        return self.db.scalar(
            self._scope(select(User).where(User.id == id_)).options(*_EAGER_OPTIONS)
        )

    def get_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup, since email is a login identifier."""
        return self.db.scalar(
            self._scope(select(User).where(func.lower(User.email) == email.strip().lower()))
        )

    def get_by_username(self, username: str) -> User | None:
        """Case-insensitive lookup by username."""
        return self.db.scalar(
            self._scope(
                select(User).where(func.lower(User.username) == username.strip().lower())
            )
        )

    def get_by_username_or_email(self, identifier: str, company_id: int) -> User | None:
        """Case-insensitive lookup matching either username or email, scoped
        to one company by an explicit parameter rather than this
        repository's own construction-time company_id.

        Lets ``username`` remain the one documented login field while still
        accepting an email address, without adding a second login field.

        The company_id is required here (unlike this class's other methods,
        which fall back to construction-time scoping) because
        AuthService.login resolves the company fresh on every call from the
        request's company_code, not once when the repository is built -
        username/email are only unique *within* a company
        (UNIQUE(company_id, username/email)), so an unscoped lookup here
        would be ambiguous the moment two companies share a username.
        """
        normalized = identifier.strip().lower()
        return self.db.scalar(
            select(User).where(
                User.company_id == company_id,
                or_(
                    func.lower(User.username) == normalized,
                    func.lower(User.email) == normalized,
                ),
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
        stmt = self._scope(select(User)).options(*_EAGER_OPTIONS)
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
