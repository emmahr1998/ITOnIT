from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.priority import PriorityRepository
from app.services.priority_service import PriorityService


def get_priority_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> PriorityRepository:
    return PriorityRepository(db, company_id)


def get_priority_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> PriorityService:
    return PriorityService(db, company_id)
