from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.inventory_item import InventoryItemRepository
from app.services.inventory_item_service import InventoryItemService


def get_inventory_item_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryItemRepository:
    return InventoryItemRepository(db, company_id)


def get_inventory_item_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryItemService:
    return InventoryItemService(db, company_id)
