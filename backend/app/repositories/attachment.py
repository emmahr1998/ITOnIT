from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.repositories.base import CompanyScopedRepository


class AttachmentRepository(CompanyScopedRepository[Attachment]):
    """Attachment persistence: eager-loaded reads for the nested uploader
    summary. Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Attachment, company_id)

    def get_by_id(self, id_: int) -> Attachment | None:
        """Overrides CompanyScopedRepository.get_by_id to additionally
        eager-load the uploader, avoiding an N+1 query when the attachment
        is serialized."""
        return self.db.scalar(
            select(Attachment)
            .where(Attachment.id == id_, Attachment.company_id == self.company_id)
            .options(selectinload(Attachment.uploaded_by))
        )

    def list_for_ticket(self, ticket_id: int) -> list[Attachment]:
        return list(
            self.db.scalars(
                select(Attachment)
                .where(
                    Attachment.ticket_id == ticket_id,
                    Attachment.company_id == self.company_id,
                )
                .options(selectinload(Attachment.uploaded_by))
                .order_by(Attachment.created_at.asc(), Attachment.id.asc())
            ).all()
        )
