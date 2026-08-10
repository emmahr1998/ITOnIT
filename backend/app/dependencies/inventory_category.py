from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.inventory_category import InventoryCategoryRepository
from app.services.inventory_category_service import InventoryCategoryService


def get_inventory_category_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryCategoryRepository:
    return InventoryCategoryRepository(db, company_id)


def get_inventory_category_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryCategoryService:
    return InventoryCategoryService(db, company_id)
