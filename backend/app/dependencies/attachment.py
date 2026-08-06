from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.repositories.attachment import AttachmentRepository
from app.services.attachment_service import AttachmentService


def get_attachment_repository(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> AttachmentRepository:
    return AttachmentRepository(db, company_id)


def get_attachment_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> AttachmentService:
    return AttachmentService(db, company_id)
