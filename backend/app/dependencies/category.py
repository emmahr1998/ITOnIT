from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.category import CategoryRepository
from app.services.category_service import CategoryService


def get_category_repository(db: Session = Depends(get_db)) -> CategoryRepository:
    return CategoryRepository(db)


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db)
