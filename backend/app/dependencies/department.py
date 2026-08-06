from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.department import DepartmentRepository
from app.services.department_service import DepartmentService


def get_department_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> DepartmentRepository:
    return DepartmentRepository(db, company_id)


def get_department_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> DepartmentService:
    return DepartmentService(db, company_id)
