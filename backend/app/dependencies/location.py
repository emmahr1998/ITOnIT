from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.location import LocationRepository
from app.services.location_service import LocationService


def get_location_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> LocationRepository:
    return LocationRepository(db, company_id)


def get_location_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> LocationService:
    return LocationService(db, company_id)
