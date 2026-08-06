from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.priority import PriorityRepository
from app.services.priority_service import PriorityService


def get_priority_repository(db: Session = Depends(get_db)) -> PriorityRepository:
    return PriorityRepository(db)


def get_priority_service(db: Session = Depends(get_db)) -> PriorityService:
    return PriorityService(db)
