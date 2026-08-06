from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Priority(TimestampMixin, Base):
    """A ticket priority level (e.g. Low, Medium, High, Critical).

    Replaces the previous TicketPriority enum column with a real table, so
    priorities can be managed (added/renamed) without a code change.
    """

    __tablename__ = "priorities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="priority")
