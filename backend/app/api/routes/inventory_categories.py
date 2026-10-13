from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_inventory_category_service, require_roles
from app.models.user import User
from app.schemas.inventory_category import (
    InventoryCategoryCreate,
    InventoryCategoryResponse,
    InventoryCategoryUpdate,
)
from app.schemas.response import DataResponse
from app.services.inventory_category_service import (
    InventoryCategoryNameConflictError,
    InventoryCategoryNotFoundError,
    InventoryCategoryService,
)

router = APIRouter(prefix="/inventory-categories", tags=["Inventory Categories"])

# Employee has no inventory access at all (not even read) - unlike
# Categories/Departments/Locations/Priorities, which every role can view.
_VIEW_ROLES = ("Technician", "Company Administrator")
_MANAGE_ROLES = ("Company Administrator",)


@router.get("", response_model=DataResponse[list[InventoryCategoryResponse]])
def list_inventory_categories(
    inventory_category_service: InventoryCategoryService = Depends(get_inventory_category_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[list[InventoryCategoryResponse]]:
    categories = inventory_category_service.list_categories()
    return DataResponse(
        data=[InventoryCategoryResponse.model_validate(c) for c in categories],
        msg="Inventory categories list fetched successfully",
    )


@router.get("/{category_id}", response_model=DataResponse[InventoryCategoryResponse])
def get_inventory_category(
    category_id: int,
    inventory_category_service: InventoryCategoryService = Depends(get_inventory_category_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[InventoryCategoryResponse]:
    try:
        category = inventory_category_service.get_category(category_id)
    except InventoryCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory category not found") from exc
    return DataResponse(
        data=InventoryCategoryResponse.model_validate(category),
        msg="Inventory category fetched successfully",
    )


@router.post(
    "", response_model=DataResponse[InventoryCategoryResponse], status_code=status.HTTP_201_CREATED
)
def create_inventory_category(
    payload: InventoryCategoryCreate,
    inventory_category_service: InventoryCategoryService = Depends(get_inventory_category_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[InventoryCategoryResponse]:
    try:
        category = inventory_category_service.create_category(payload)
    except InventoryCategoryNameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An inventory category with this name already exists"
        ) from exc
    return DataResponse(
        data=InventoryCategoryResponse.model_validate(category),
        msg="Inventory category created successfully",
    )


@router.patch("/{category_id}", response_model=DataResponse[InventoryCategoryResponse])
def update_inventory_category(
    category_id: int,
    payload: InventoryCategoryUpdate,
    inventory_category_service: InventoryCategoryService = Depends(get_inventory_category_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[InventoryCategoryResponse]:
    try:
        category = inventory_category_service.update_category(category_id, payload)
    except InventoryCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory category not found") from exc
    except InventoryCategoryNameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An inventory category with this name already exists"
        ) from exc
    return DataResponse(
        data=InventoryCategoryResponse.model_validate(category),
        msg="Inventory category updated successfully",
    )
