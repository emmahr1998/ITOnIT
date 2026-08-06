from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket


class Priority(TimestampMixin, Base):
    """A ticket priority level (e.g. Low, Medium, High, Critical).

    Company-owned: title is unique per company. A starter set (Low/Medium/
    High/Critical) is seeded for every new company at registration; the
    Company Administrator may add, rename, or remove their own company's
    priorities after that - this is company data, not a shared platform
    constant, despite every company starting from the same starter list.
    """

    __tablename__ = "priorities"
    __table_args__ = (UniqueConstraint("company_id", "title", name="uq_priorities_company_id_title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(50), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="priorities")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="priority")
