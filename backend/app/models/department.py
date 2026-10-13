from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class Department(TimestampMixin, Base):
    """An organizational department a user may belong to (e.g. IT, Finance).

    Company-owned: title is unique per company, not platform-wide, so two
    different companies may each have their own "IT" department.
    """

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "title", name="uq_departments_company_id_title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="departments")
    users: Mapped[list["User"]] = relationship(back_populates="department")
