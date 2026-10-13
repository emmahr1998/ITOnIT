from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.history import HistoryRepository
from app.services.history_service import HistoryService


def get_history_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> HistoryRepository:
    return HistoryRepository(db, company_id)


def get_history_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> HistoryService:
    return HistoryService(db, company_id)
