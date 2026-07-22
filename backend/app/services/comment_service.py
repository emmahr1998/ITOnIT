from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.comment import Comment
from app.models.user import User
from app.repositories.comment import CommentRepository
from app.services.history_service import HistoryService

_MANAGE_ROLE_NAMES = ("Manager", "Administrator")


class CommentNotFoundError(Exception):
    """Raised when a comment id does not exist, or does not belong to the given ticket."""


class CommentPermissionError(Exception):
    """Raised when a non-owning, non-manage-role user tries to edit/delete a comment."""


class CommentService:
    """Owns comment ownership rules: who may edit/delete which comment.

    Ticket-level access (can this user see/comment on this ticket at all) is
    verified by the route via TicketService/get_viewable_ticket before this
    is ever called - this service only answers comment-level questions, so
    that check is never duplicated here.

    Also owns the transaction boundary for comment writes (same convention
    as CategoryService/TicketService), and drives TicketHistory recording
    for every comment mutation via HistoryService.
    """

    def __init__(
        self,
        db: Session,
        comment_repository: CommentRepository | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        self._db = db
        self._comment_repository = (
            comment_repository if comment_repository is not None else CommentRepository(db)
        )
        self._history_service = (
            history_service if history_service is not None else HistoryService(db)
        )

    @staticmethod
    def _is_manage_role(user: User) -> bool:
        return user.role.name in _MANAGE_ROLE_NAMES

    def list_comments(self, ticket_id: int) -> list[Comment]:
        return self._comment_repository.list_for_ticket(ticket_id)

    def _get_owned_comment(self, ticket_id: int, comment_id: int) -> Comment:
        comment = self._comment_repository.get_by_id(comment_id)
        if comment is None or comment.ticket_id != ticket_id:
            raise CommentNotFoundError
        return comment

    def add_comment(self, current_user: User, ticket_id: int, content: str) -> Comment:
        comment = Comment(ticket_id=ticket_id, author_user_id=current_user.id, content=content)
        comment.author = current_user
        self._comment_repository.create(comment)
        self._history_service.record(ticket_id, current_user, "comment_added", None, content)
        self._db.commit()
        return comment

    def update_comment(
        self, current_user: User, ticket_id: int, comment_id: int, content: str
    ) -> Comment:
        comment = self._get_owned_comment(ticket_id, comment_id)
        if not self._is_manage_role(current_user) and comment.author_user_id != current_user.id:
            raise CommentPermissionError

        old_content = comment.content
        comment.content = content
        comment.updated_at = datetime.now(timezone.utc)
        self._comment_repository.update(comment)
        self._history_service.record(
            ticket_id, current_user, "comment_edited", old_content, content
        )
        self._db.commit()
        return comment

    def delete_comment(self, current_user: User, ticket_id: int, comment_id: int) -> None:
        comment = self._get_owned_comment(ticket_id, comment_id)
        if not self._is_manage_role(current_user) and comment.author_user_id != current_user.id:
            raise CommentPermissionError

        old_content = comment.content
        self._comment_repository.delete(comment)
        self._history_service.record(
            ticket_id, current_user, "comment_deleted", old_content, None
        )
        self._db.commit()
