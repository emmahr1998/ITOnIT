from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.comment import Comment
from app.repositories.base import CompanyScopedRepository


class CommentRepository(CompanyScopedRepository[Comment]):
    """Comment persistence: eager-loaded reads for the nested author summary.
    Company-scoped - see CompanyScopedRepository."""

    def __init__(self, db: Session, company_id: int) -> None:
        super().__init__(db, Comment, company_id)

    def get_by_id(self, id_: int) -> Comment | None:
        """Overrides CompanyScopedRepository.get_by_id to additionally
        eager-load the author, avoiding an N+1 query when the comment is
        serialized."""
        return self.db.scalar(
            select(Comment)
            .where(Comment.id == id_, Comment.company_id == self.company_id)
            .options(selectinload(Comment.author))
        )

    def list_for_ticket(self, ticket_id: int) -> list[Comment]:
        return list(
            self.db.scalars(
                select(Comment)
                .where(Comment.ticket_id == ticket_id, Comment.company_id == self.company_id)
                .options(selectinload(Comment.author))
                .order_by(Comment.created_at.asc(), Comment.id.asc())
            ).all()
        )
