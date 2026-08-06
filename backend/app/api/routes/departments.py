from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_active_user, get_department_service, require_roles
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.schemas.response import DataResponse
from app.services.department_service import (
    DepartmentNotFoundError,
    DepartmentService,
    DepartmentTitleConflictError,
)

router = APIRouter(prefix="/departments", tags=["Departments"])

_MANAGE_ROLES = ("Company Administrator",)


@router.get("", response_model=DataResponse[list[DepartmentResponse]])
def list_departments(
    department_service: DepartmentService = Depends(get_department_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[list[DepartmentResponse]]:
    departments = department_service.list_departments()
    return DataResponse(
        data=[DepartmentResponse.model_validate(d) for d in departments],
        msg="Departments list fetched successfully",
    )


@router.get("/{department_id}", response_model=DataResponse[DepartmentResponse])
def get_department(
    department_id: int,
    department_service: DepartmentService = Depends(get_department_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[DepartmentResponse]:
    try:
        department = department_service.get_department(department_id)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found") from exc
    return DataResponse(
        data=DepartmentResponse.model_validate(department),
        msg="Department fetched successfully",
    )


@router.post(
    "", response_model=DataResponse[DepartmentResponse], status_code=status.HTTP_201_CREATED
)
def create_department(
    payload: DepartmentCreate,
    department_service: DepartmentService = Depends(get_department_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[DepartmentResponse]:
    try:
        department = department_service.create_department(payload)
    except DepartmentTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A department with this title already exists"
        ) from exc
    return DataResponse(
        data=DepartmentResponse.model_validate(department),
        msg="Department created successfully",
    )


@router.patch("/{department_id}", response_model=DataResponse[DepartmentResponse])
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    department_service: DepartmentService = Depends(get_department_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[DepartmentResponse]:
    try:
        department = department_service.update_department(department_id, payload)
    except DepartmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found") from exc
    except DepartmentTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A department with this title already exists"
        ) from exc
    return DataResponse(
        data=DepartmentResponse.model_validate(department),
        msg="Department updated successfully",
    )
