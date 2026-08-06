from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_active_user, get_user_service, require_roles
from app.models.user import User
from app.schemas.response import DataResponse
from app.schemas.user import (
    AdminPasswordSetRequest,
    PasswordChangeRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import (
    EmailConflictError,
    InvalidCurrentPasswordError,
    InvalidDepartmentError,
    InvalidRoleError,
    UserNotFoundError,
    UserPermissionError,
    UserService,
    UsernameConflictError,
)

router = APIRouter(prefix="/users", tags=["Users"])

_MANAGE_ROLES = ("Company Administrator",)


@router.post("", response_model=DataResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
    _current_user: User = Depends(require_roles("Company Administrator")),
) -> DataResponse[UserResponse]:
    try:
        user = user_service.create_user(payload)
    except UsernameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this username already exists"
        ) from exc
    except EmailConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        ) from exc
    except InvalidRoleError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role_id does not exist") from exc
    except InvalidDepartmentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "department_id does not exist"
        ) from exc
    return DataResponse(data=UserResponse.model_validate(user), msg="User created successfully")


@router.get("", response_model=DataResponse[list[UserResponse]])
def list_users(
    role_id: int | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user_service: UserService = Depends(get_user_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[list[UserResponse]]:
    users, total = user_service.list_users(
        role_id=role_id,
        department_id=department_id,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )
    return DataResponse(
        data=[UserResponse.model_validate(u) for u in users],
        msg=f"Fetched {len(users)} of {total} users",
    )


@router.get("/{user_id}", response_model=DataResponse[UserResponse])
def get_user(
    user_id: int,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> DataResponse[UserResponse]:
    try:
        user = user_service.get_user_for_viewer(user_id, current_user)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    except UserPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have permission to view this user"
        ) from exc
    return DataResponse(data=UserResponse.model_validate(user), msg="User fetched successfully")


@router.patch("/{user_id}", response_model=DataResponse[UserResponse])
def update_user(
    user_id: int,
    payload: UserUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> DataResponse[UserResponse]:
    try:
        user = user_service.update_user(user_id, payload, current_user=current_user)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    except UserPermissionError as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have permission to edit this user"
        ) from exc
    except UsernameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this username already exists"
        ) from exc
    except EmailConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A user with this email already exists"
        ) from exc
    except InvalidRoleError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role_id does not exist") from exc
    except InvalidDepartmentError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "department_id does not exist"
        ) from exc
    return DataResponse(data=UserResponse.model_validate(user), msg="User updated successfully")


@router.patch("/me/password", response_model=DataResponse[None])
def change_own_password(
    payload: PasswordChangeRequest,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user),
) -> DataResponse[None]:
    try:
        user_service.change_own_password(current_user.id, payload)
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Current password is incorrect"
        ) from exc
    return DataResponse(data=None, msg="Password changed successfully")


@router.patch("/{user_id}/password", response_model=DataResponse[None])
def admin_set_password(
    user_id: int,
    payload: AdminPasswordSetRequest,
    user_service: UserService = Depends(get_user_service),
    _current_user: User = Depends(require_roles("Company Administrator")),
) -> DataResponse[None]:
    try:
        user_service.admin_set_password(user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found") from exc
    return DataResponse(data=None, msg="Password updated successfully")
