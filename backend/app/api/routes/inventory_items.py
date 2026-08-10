from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_inventory_item_service, require_roles
from app.models.enums import InventoryCondition, InventoryStatus, InventoryTrackingType
from app.models.user import User
from app.schemas.inventory_item import InventoryItemCreate, InventoryItemResponse, InventoryItemUpdate
from app.schemas.response import DataResponse
from app.services.inventory_item_service import (
    InventoryCategoryInactiveError,
    InventoryCategoryNotFoundError,
    InventoryItemAssetTagConflictError,
    InventoryItemHolderNotFoundError,
    InventoryItemLocationNotFoundError,
    InventoryItemNotFoundError,
    InventoryItemService,
    InventoryItemValidationError,
)

router = APIRouter(prefix="/inventory-items", tags=["Inventory Items"])

# Employee has no inventory access at all - matches Inventory Categories.
_VIEW_ROLES = ("Technician", "Company Administrator")
_MANAGE_ROLES = ("Company Administrator",)


@router.get("", response_model=DataResponse[list[InventoryItemResponse]])
def list_inventory_items(
    inventory_category_id: int | None = Query(default=None),
    tracking_type: InventoryTrackingType | None = Query(default=None),
    status_: InventoryStatus | None = Query(default=None, alias="status"),
    condition: InventoryCondition | None = Query(default=None),
    current_location_id: int | None = Query(default=None),
    current_holder_user_id: int | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    model: str | None = Query(default=None),
    search: str | None = Query(default=None),
    low_stock: bool | None = Query(default=None),
    warranty_expiring_days: int | None = Query(default=None, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    inventory_item_service: InventoryItemService = Depends(get_inventory_item_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[list[InventoryItemResponse]]:
    items, total = inventory_item_service.list_items(
        inventory_category_id=inventory_category_id,
        tracking_type=tracking_type,
        status=status_,
        condition=condition,
        current_location_id=current_location_id,
        current_holder_user_id=current_holder_user_id,
        manufacturer=manufacturer,
        model=model,
        search=search,
        low_stock=low_stock,
        warranty_expiring_days=warranty_expiring_days,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=limit,
    )
    return DataResponse(
        data=[InventoryItemResponse.model_validate(item) for item in items],
        msg=f"Fetched {len(items)} of {total} inventory items",
    )


@router.get("/{item_id}", response_model=DataResponse[InventoryItemResponse])
def get_inventory_item(
    item_id: int,
    inventory_item_service: InventoryItemService = Depends(get_inventory_item_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> DataResponse[InventoryItemResponse]:
    try:
        item = inventory_item_service.get_item(item_id)
    except InventoryItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found") from exc
    return DataResponse(
        data=InventoryItemResponse.model_validate(item), msg="Inventory item fetched successfully"
    )


@router.post(
    "", response_model=DataResponse[InventoryItemResponse], status_code=status.HTTP_201_CREATED
)
def create_inventory_item(
    payload: InventoryItemCreate,
    inventory_item_service: InventoryItemService = Depends(get_inventory_item_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[InventoryItemResponse]:
    try:
        item = inventory_item_service.create_item(payload)
    except InventoryItemAssetTagConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An inventory item with this asset tag already exists"
        ) from exc
    except InventoryCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inventory category not found") from exc
    except InventoryCategoryInactiveError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Inventory category is deactivated and cannot be assigned",
        ) from exc
    except InventoryItemLocationNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Location not found") from exc
    except InventoryItemHolderNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Holder user not found") from exc
    except InventoryItemValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc
    return DataResponse(
        data=InventoryItemResponse.model_validate(item), msg="Inventory item created successfully"
    )


@router.patch("/{item_id}", response_model=DataResponse[InventoryItemResponse])
def update_inventory_item(
    item_id: int,
    payload: InventoryItemUpdate,
    inventory_item_service: InventoryItemService = Depends(get_inventory_item_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> DataResponse[InventoryItemResponse]:
    try:
        item = inventory_item_service.update_item(item_id, payload)
    except InventoryItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found") from exc
    except InventoryItemAssetTagConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An inventory item with this asset tag already exists"
        ) from exc
    except InventoryCategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inventory category not found") from exc
    except InventoryCategoryInactiveError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Inventory category is deactivated and cannot be assigned",
        ) from exc
    except InventoryItemLocationNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Location not found") from exc
    except InventoryItemHolderNotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Holder user not found") from exc
    except InventoryItemValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc
    return DataResponse(
        data=InventoryItemResponse.model_validate(item), msg="Inventory item updated successfully"
    )
