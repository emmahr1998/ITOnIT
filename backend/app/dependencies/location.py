from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.location import LocationRepository
from app.services.location_service import LocationService


def get_location_repository(db: Session = Depends(get_db)) -> LocationRepository:
    return LocationRepository(db)


def get_location_service(db: Session = Depends(get_db)) -> LocationService:
    return LocationService(db)
