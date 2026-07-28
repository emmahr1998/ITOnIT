from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.department import DepartmentRepository
from app.services.department_service import DepartmentService


def get_department_repository(db: Session = Depends(get_db)) -> DepartmentRepository:
    return DepartmentRepository(db)


def get_department_service(db: Session = Depends(get_db)) -> DepartmentService:
    return DepartmentService(db)
