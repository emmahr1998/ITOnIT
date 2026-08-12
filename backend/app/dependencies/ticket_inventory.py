from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.ticket_inventory_usage import TicketInventoryUsageRepository
from app.services.ticket_inventory_service import TicketInventoryService


def get_ticket_inventory_usage_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> TicketInventoryUsageRepository:
    return TicketInventoryUsageRepository(db, company_id)


def get_ticket_inventory_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> TicketInventoryService:
    return TicketInventoryService(db, company_id)
