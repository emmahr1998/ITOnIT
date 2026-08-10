from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.inventory_item import InventoryItem


class InventoryCategory(CreatedAtMixin, Base):
    """Classifies inventory items by asset type (e.g. Laptop, Monitor,
    Cable) - distinct from Category, which classifies tickets by issue type
    (Hardware, Software, ...). The two serve different purposes and are
    deliberately not the same table.

    Company-owned: name is unique per company. A starter set is seeded for
    every new company at registration (see CompanyService._seed_defaults);
    the Company Administrator may add, rename, or deactivate their own
    company's inventory categories afterward, same as Category/Location.
    """

    __tablename__ = "inventory_categories"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_inventory_categories_company_id_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    company: Mapped["Company"] = relationship(back_populates="inventory_categories")
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="inventory_category"
    )
