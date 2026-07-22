from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.comment import CommentRepository
from app.services.comment_service import CommentService


def get_comment_repository(db: Session = Depends(get_db)) -> CommentRepository:
    return CommentRepository(db)


def get_comment_service(db: Session = Depends(get_db)) -> CommentService:
    return CommentService(db)
