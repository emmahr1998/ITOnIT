from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.services.inventory_transaction_service import InventoryTransactionService


def get_inventory_transaction_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryTransactionRepository:
    return InventoryTransactionRepository(db, company_id)


def get_inventory_transaction_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> InventoryTransactionService:
    return InventoryTransactionService(db, company_id)
