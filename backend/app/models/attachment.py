from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket
    from app.models.user import User


class Attachment(CreatedAtMixin, Base):
    """Metadata for a file uploaded to a ticket.

    The file itself is stored outside SQL Server; only its metadata and
    storage location are persisted here. An attachment belongs to exactly
    one entity - its ticket - not optionally to a comment as well.

    company_id is denormalized from the parent ticket - see Comment's
    docstring for why every tenant-owned row carries it.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    company: Mapped["Company"] = relationship()
    ticket: Mapped["Ticket"] = relationship(back_populates="attachments")
    uploaded_by: Mapped["User"] = relationship(back_populates="attachments")
