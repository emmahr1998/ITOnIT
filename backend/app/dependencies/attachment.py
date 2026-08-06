from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.attachment import AttachmentRepository
from app.services.attachment_service import AttachmentService


def get_attachment_repository(db: Session = Depends(get_db)) -> AttachmentRepository:
    return AttachmentRepository(db)


def get_attachment_service(db: Session = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)
