from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.comment import CommentRepository
from app.services.comment_service import CommentService


def get_comment_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> CommentRepository:
    return CommentRepository(db, company_id)


def get_comment_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> CommentService:
    return CommentService(db, company_id)
