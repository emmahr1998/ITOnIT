from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.department import Department
    from app.models.inventory_category import InventoryCategory
    from app.models.inventory_item import InventoryItem
    from app.models.location import Location
    from app.models.priority import Priority
    from app.models.ticket import Ticket
    from app.models.user import User


class Company(TimestampMixin, Base):
    """A tenant: one customer organization using ITOnIT.

    Every user (other than the single platform-level System Administrator,
    for whom company_id is null), ticket, department, category, location,
    and priority belongs to exactly one company. Isolation between
    companies is enforced by CompanyScopedRepository filtering every query
    by company_id - this model itself carries no isolation logic, it is
    just the row every other tenant-owned row points back to.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="light", server_default="light")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC", server_default="UTC")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", server_default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    users: Mapped[list["User"]] = relationship(back_populates="company")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="company")
    departments: Mapped[list["Department"]] = relationship(back_populates="company")
    categories: Mapped[list["Category"]] = relationship(back_populates="company")
    locations: Mapped[list["Location"]] = relationship(back_populates="company")
    priorities: Mapped[list["Priority"]] = relationship(back_populates="company")
    inventory_categories: Mapped[list["InventoryCategory"]] = relationship(
        back_populates="company"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="company")
