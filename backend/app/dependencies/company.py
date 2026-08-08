from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.company import CompanyRepository
from app.services.company_service import CompanyService


def get_company_repository(db: Session = Depends(get_db)) -> CompanyRepository:
    return CompanyRepository(db)


def get_company_service(db: Session = Depends(get_db)) -> CompanyService:
    return CompanyService(db)
