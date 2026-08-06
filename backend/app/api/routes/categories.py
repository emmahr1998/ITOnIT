from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_category_service, require_roles
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category_service import (
    CategoryInUseError,
    CategoryNameConflictError,
    CategoryNotFoundError,
    CategoryService,
)

router = APIRouter(prefix="/categories", tags=["Categories"])

_VIEW_ROLES = ("Employee", "Technician", "Manager", "Administrator")
_MANAGE_ROLES = ("Manager", "Administrator")


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    category_service: CategoryService = Depends(get_category_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> list[CategoryResponse]:
    categories = category_service.list_categories()
    return [CategoryResponse.model_validate(category) for category in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    category_service: CategoryService = Depends(get_category_service),
    _current_user: User = Depends(require_roles(*_VIEW_ROLES)),
) -> CategoryResponse:
    try:
        category = category_service.get_category(category_id)
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    return CategoryResponse.model_validate(category)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    category_service: CategoryService = Depends(get_category_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> CategoryResponse:
    try:
        category = category_service.create_category(payload)
    except CategoryNameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A category with this name already exists"
        ) from exc
    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    category_service: CategoryService = Depends(get_category_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> CategoryResponse:
    try:
        category = category_service.update_category(category_id, payload)
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except CategoryNameConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A category with this name already exists"
        ) from exc
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    category_service: CategoryService = Depends(get_category_service),
    _current_user: User = Depends(require_roles(*_MANAGE_ROLES)),
) -> None:
    try:
        category_service.delete_category(category_id)
    except CategoryNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found") from exc
    except CategoryInUseError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot delete category: it is still referenced by one or more tickets",
        ) from exc
