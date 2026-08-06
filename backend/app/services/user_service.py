from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.repositories.department import DepartmentRepository
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.user import AdminPasswordSetRequest, PasswordChangeRequest, UserCreate, UserUpdate

# Fields a user may change on their own profile via PATCH /users/{id}.
# Anything else on UserUpdate is Company-Administrator-only.
_SELF_EDITABLE_FIELDS = frozenset({"first_name", "last_name", "phone_number", "theme"})
_MANAGE_ROLES = frozenset({"Company Administrator"})


class UserNotFoundError(Exception):
    """Raised when a user id does not exist."""


class UsernameConflictError(Exception):
    """Raised when a username is already taken by another user."""


class EmailConflictError(Exception):
    """Raised when an email is already taken by another user."""


class InvalidRoleError(Exception):
    """Raised when a role_id does not reference an existing role."""


class InvalidDepartmentError(Exception):
    """Raised when a department_id does not reference an existing department."""


class UserPermissionError(Exception):
    """Raised when a non-admin tries to edit another user, or tries to set
    an administrative field on their own profile.
    """


class InvalidCurrentPasswordError(Exception):
    """Raised when a self-service password change supplies the wrong
    current password.
    """


class UserService:
    """Owns user business rules: username/email uniqueness, role/department
    validation, the admin-vs-self field split on updates, and password
    changes.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input -
    every user this service reads, writes, or checks uniqueness against is
    confined to it. role_repository is deliberately NOT scoped: roles
    (Employee/Technician/Company Administrator/System Administrator) are
    shared platform vocabulary, not company-owned data.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
        department_repository: DepartmentRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._user_repository = (
            user_repository if user_repository is not None else UserRepository(db, company_id)
        )
        self._role_repository = (
            role_repository if role_repository is not None else RoleRepository(db)
        )
        self._department_repository = (
            department_repository
            if department_repository is not None
            else DepartmentRepository(db, company_id)
        )

    def list_users(
        self,
        *,
        role_id: int | None = None,
        department_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[User], int]:
        users = self._user_repository.get_with_filters(
            role_id=role_id,
            department_id=department_id,
            is_active=is_active,
            search=search,
            skip=skip,
            limit=limit,
        )
        total = self._user_repository.count_with_filters(
            role_id=role_id, department_id=department_id, is_active=is_active, search=search
        )
        return users, total

    def get_user(self, user_id: int) -> User:
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        return user

    def get_user_for_viewer(self, user_id: int, viewer: User) -> User:
        """GET /users/{id}: a Company Administrator may view anyone in
        their own company; everyone else may only view their own record.
        """
        if viewer.role.name not in _MANAGE_ROLES and viewer.id != user_id:
            raise UserPermissionError
        return self.get_user(user_id)

    def _get_role_or_raise(self, role_id: int) -> Role:
        role = self._role_repository.get_by_id(role_id)
        if role is None:
            raise InvalidRoleError
        return role

    def _get_department_or_raise(self, department_id: int) -> Department:
        department = self._department_repository.get_by_id(department_id)
        if department is None:
            raise InvalidDepartmentError
        return department

    def create_user(self, payload: UserCreate) -> User:
        if self._user_repository.get_by_username(payload.username) is not None:
            raise UsernameConflictError
        if self._user_repository.get_by_email(payload.email) is not None:
            raise EmailConflictError
        role = self._get_role_or_raise(payload.role_id)
        department = (
            self._get_department_or_raise(payload.department_id)
            if payload.department_id is not None
            else None
        )

        user = User(
            company_id=self._company_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone_number=payload.phone_number,
            department_id=payload.department_id,
            role_id=payload.role_id,
            theme=payload.theme,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        # Set the relationship objects directly rather than relying on a
        # later lazy-load through the FK - correct immediately, with no
        # dependency on session/refresh timing (see TicketService for the
        # same convention).
        user.role = role
        user.department = department
        try:
            self._user_repository.create(user)
            self._db.commit()
        except IntegrityError as exc:
            # Defense in depth: a concurrent request could pass the checks
            # above and lose the race to the database's unique constraints.
            self._db.rollback()
            raise UsernameConflictError from exc
        return user

    def update_user(self, user_id: int, payload: UserUpdate, *, current_user: User) -> User:
        """Apply a partial update, enforcing the admin-vs-self field split.

        A Company Administrator may set any field on any user in their own
        company - any number of Company Administrators may exist per
        company, all with identical permissions here. Anyone else may only
        edit their own profile (user_id == current_user.id), and only
        the "safe" fields in _SELF_EDITABLE_FIELDS - submitting any other
        field with a non-None value is rejected outright rather than
        silently ignored.
        """
        is_admin = current_user.role.name == "Company Administrator"
        fields_set = payload.model_fields_set

        if not is_admin:
            if user_id != current_user.id:
                raise UserPermissionError
            disallowed = fields_set - _SELF_EDITABLE_FIELDS
            if disallowed:
                raise UserPermissionError

        user = self.get_user(user_id)

        if "username" in fields_set and payload.username is not None:
            duplicate = self._user_repository.get_by_username(payload.username)
            if duplicate is not None and duplicate.id != user_id:
                raise UsernameConflictError
            user.username = payload.username
        if "email" in fields_set and payload.email is not None:
            duplicate = self._user_repository.get_by_email(payload.email)
            if duplicate is not None and duplicate.id != user_id:
                raise EmailConflictError
            user.email = payload.email
        if "role_id" in fields_set and payload.role_id is not None:
            role = self._get_role_or_raise(payload.role_id)
            user.role_id = payload.role_id
            user.role = role
        if "department_id" in fields_set:
            department = (
                self._get_department_or_raise(payload.department_id)
                if payload.department_id is not None
                else None
            )
            user.department_id = payload.department_id
            user.department = department
        if "is_active" in fields_set and payload.is_active is not None:
            user.is_active = payload.is_active
        if "first_name" in fields_set and payload.first_name is not None:
            user.first_name = payload.first_name
        if "last_name" in fields_set and payload.last_name is not None:
            user.last_name = payload.last_name
        if "phone_number" in fields_set:
            user.phone_number = payload.phone_number
        if "theme" in fields_set:
            user.theme = payload.theme

        try:
            self._user_repository.update(user)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise UsernameConflictError from exc
        return user

    def change_own_password(
        self, user_id: int, payload: PasswordChangeRequest
    ) -> None:
        user = self.get_user(user_id)
        if not verify_password(payload.current_password, user.password_hash):
            raise InvalidCurrentPasswordError
        user.password_hash = hash_password(payload.new_password)
        self._user_repository.update(user)
        self._db.commit()

    def admin_set_password(self, user_id: int, payload: AdminPasswordSetRequest) -> None:
        user = self.get_user(user_id)
        user.password_hash = hash_password(payload.new_password)
        self._user_repository.update(user)
        self._db.commit()
