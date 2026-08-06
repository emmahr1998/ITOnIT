from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.category import CategoryRepository
from app.services.category_service import CategoryService


def get_category_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> CategoryRepository:
    return CategoryRepository(db, company_id)


def get_category_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> CategoryService:
    return CategoryService(db, company_id)
