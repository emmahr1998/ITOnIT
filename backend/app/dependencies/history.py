from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.history import HistoryRepository
from app.services.history_service import HistoryService


def get_history_repository(db: Session = Depends(get_db)) -> HistoryRepository:
    return HistoryRepository(db)


def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(db)
