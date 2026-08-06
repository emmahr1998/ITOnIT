from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_active_user, get_priority_service, require_roles
from app.models.user import User
from app.schemas.priority import PriorityCreate, PriorityResponse, PriorityUpdate
from app.schemas.response import DataResponse
from app.services.priority_service import (
    PriorityNotFoundError,
    PriorityService,
    PriorityTitleConflictError,
)

router = APIRouter(prefix="/priorities", tags=["Priorities"])

_MANAGE_ROLES = ("Manager", "Administrator")


@router.get("", response_model=DataResponse[list[PriorityResponse]])
def list_priorities(
    priority_service: PriorityService = Depends(get_priority_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[list[PriorityResponse]]:
    priorities = priority_service.list_priorities()
    return DataResponse(
        data=[PriorityResponse.model_validate(p) for p in priorities],
        msg="Priorities list fetched successfully",
    )


@router.get("/{priority_id}", response_model=DataResponse[PriorityResponse])
def get_priority(
    priority_id: int,
    priority_service: PriorityService = Depends(get_priority_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[PriorityResponse]:
    try:
        priority = priority_service.get_priority(priority_id)
    except PriorityNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Priority not found") from exc
    return DataResponse(
        data=PriorityResponse.model_validate(priority), msg="Priority fetched successfully"
    )


@router.post(
    "", response_model=DataResponse[PriorityResponse], status_code=status.HTTP_201_CREATED
)
def create_priority(
    payload: PriorityCreate,
    priority_service: PriorityService = Depends(get_priority_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[PriorityResponse]:
    try:
        priority = priority_service.create_priority(payload)
    except PriorityTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A priority with this title already exists"
        ) from exc
    return DataResponse(
        data=PriorityResponse.model_validate(priority), msg="Priority created successfully"
    )


@router.patch("/{priority_id}", response_model=DataResponse[PriorityResponse])
def update_priority(
    priority_id: int,
    payload: PriorityUpdate,
    priority_service: PriorityService = Depends(get_priority_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[PriorityResponse]:
    try:
        priority = priority_service.update_priority(priority_id, payload)
    except PriorityNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Priority not found") from exc
    except PriorityTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A priority with this title already exists"
        ) from exc
    return DataResponse(
        data=PriorityResponse.model_validate(priority), msg="Priority updated successfully"
    )
