from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket


class Category(CreatedAtMixin, Base):
    """Classifies tickets by the type of issue being reported (e.g. Hardware, Network).

    Company-owned: name is unique per company. A starter set is seeded for
    every new company at registration; the Company Administrator may add,
    rename, or deactivate their own company's categories after that.
    """

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_categories_company_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    company: Mapped["Company"] = relationship(back_populates="categories")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category")
