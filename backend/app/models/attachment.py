from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.ticket import Ticket
    from app.models.user import User


class Attachment(CreatedAtMixin, Base):
    """Metadata for a file uploaded to a ticket or comment.

    The file itself is stored outside SQL Server; only its metadata and
    storage location are persisted here.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="attachments")
    comment: Mapped["Comment | None"] = relationship(back_populates="attachments")
    uploaded_by: Mapped["User"] = relationship(back_populates="attachments")
