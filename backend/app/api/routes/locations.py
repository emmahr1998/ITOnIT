from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_active_user, get_location_service, require_roles
from app.models.user import User
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.response import DataResponse
from app.services.location_service import (
    LocationNotFoundError,
    LocationService,
    LocationTitleConflictError,
)

router = APIRouter(prefix="/locations", tags=["Locations"])

_MANAGE_ROLES = ("Company Administrator",)


@router.get("", response_model=DataResponse[list[LocationResponse]])
def list_locations(
    location_service: LocationService = Depends(get_location_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[list[LocationResponse]]:
    locations = location_service.list_locations()
    return DataResponse(
        data=[LocationResponse.model_validate(location) for location in locations],
        msg="Locations list fetched successfully",
    )


@router.get("/{location_id}", response_model=DataResponse[LocationResponse])
def get_location(
    location_id: int,
    location_service: LocationService = Depends(get_location_service),
    _current_user: User = Depends(get_current_active_user),
) -> DataResponse[LocationResponse]:
    try:
        location = location_service.get_location(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found") from exc
    return DataResponse(
        data=LocationResponse.model_validate(location), msg="Location fetched successfully"
    )


@router.post(
    "", response_model=DataResponse[LocationResponse], status_code=status.HTTP_201_CREATED
)
def create_location(
    payload: LocationCreate,
    location_service: LocationService = Depends(get_location_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[LocationResponse]:
    try:
        location = location_service.create_location(payload)
    except LocationTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A location with this title already exists"
        ) from exc
    return DataResponse(
        data=LocationResponse.model_validate(location), msg="Location created successfully"
    )


@router.patch("/{location_id}", response_model=DataResponse[LocationResponse])
def update_location(
    location_id: int,
    payload: LocationUpdate,
    location_service: LocationService = Depends(get_location_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[LocationResponse]:
    try:
        location = location_service.update_location(location_id, payload)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found") from exc
    except LocationTitleConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A location with this title already exists"
        ) from exc
    return DataResponse(
        data=LocationResponse.model_validate(location), msg="Location updated successfully"
    )
