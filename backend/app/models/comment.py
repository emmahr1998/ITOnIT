from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket
    from app.models.user import User


class Comment(CreatedAtMixin, Base):
    """A message posted on a ticket by an employee, technician, or manager.

    company_id is denormalized from the parent ticket - a comment is always
    reached via its ticket (which is itself company-scoped), but every
    tenant-owned row carries the same column so CompanyScopedRepository's
    safety net is mechanical rather than "remember to join through the
    parent."
    """

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # No default - stays None until CommentService.update_comment sets it via
    # app.core.time.utc_now_naive on an edit. See docs/TECH_DEBT.md's UTC
    # timestamp normalization entry.
    updated_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)

    company: Mapped["Company"] = relationship()
    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")
