from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import InventoryCondition, InventoryStatus, InventoryTrackingType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.inventory_category import InventoryCategory
    from app.models.location import Location
    from app.models.user import User


class InventoryItem(TimestampMixin, Base):
    """A single unit or SKU of company-owned IT hardware/stock.

    Two tracking types share this one table rather than living in separate
    tables (see the approved Inventory ERD, Rev. 3):

    - SERIALIZED: one physical unit per row (a laptop, a monitor).
      `asset_tag` is required, `stock_quantity` is always 1,
      `reserved_quantity` is 0 or 1, and the full InventoryStatus range
      applies.
    - BULK: a SKU-level quantity of interchangeable stock (cables, mice).
      `asset_tag` is optional, `stock_quantity`/`reserved_quantity` track
      real counts, and `status` is restricted to AVAILABLE/RETIRED -
      RESERVED/IN_USE/IN_REPAIR describe a single unit's state, which
      doesn't apply to a SKU row.

    All eight rules below are enforced at two layers: the service/schema
    layer (primary - friendly, specific errors) and these CHECK constraints
    (backstop - catches anything that reaches the database another way).
    See the approved Inventory ERD, §05, for the full rationale:

      1. tracking_type <> 'SERIALIZED' OR asset_tag IS NOT NULL
      2. tracking_type <> 'SERIALIZED' OR stock_quantity = 1
      3. tracking_type <> 'SERIALIZED' OR reserved_quantity IN (0, 1)
      4. tracking_type <> 'BULK' OR status IN ('AVAILABLE', 'RETIRED')
      5. tracking_type <> 'BULK' OR current_holder_user_id IS NULL
      6. stock_quantity >= 0
      7. reserved_quantity >= 0
      8. reserved_quantity <= stock_quantity

    `asset_tag` uniqueness is a filtered unique index, not a plain UNIQUE
    constraint - see ux_inventory_items_company_id_asset_tag below and the
    ERD's §04: SQL Server's plain UNIQUE treats NULL as a comparable value
    (allowing at most one NULL per company), which would incorrectly block
    more than one untagged BULK item per company.

    Only three FKs get a real database-level ON DELETE action
    (current_location_id, current_holder_user_id - both SET NULL); every
    other FK here is NO ACTION, matching this schema's existing convention
    of handling company-teardown cascades at the application layer rather
    than via DB-level CASCADE. See the ERD's §03 for the full reasoning,
    including why this is safe under SQL Server's multiple-cascade-paths
    restriction.
    """

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index(
            "ux_inventory_items_company_id_asset_tag",
            "company_id",
            "asset_tag",
            unique=True,
            mssql_where=text("asset_tag IS NOT NULL"),
        ),
        CheckConstraint(
            "tracking_type <> 'SERIALIZED' OR asset_tag IS NOT NULL",
            name="ck_inventory_items_serialized_asset_tag",
        ),
        CheckConstraint(
            "tracking_type <> 'SERIALIZED' OR stock_quantity = 1",
            name="ck_inventory_items_serialized_stock_one",
        ),
        CheckConstraint(
            "tracking_type <> 'SERIALIZED' OR reserved_quantity IN (0, 1)",
            name="ck_inventory_items_serialized_reserved_bound",
        ),
        CheckConstraint(
            "tracking_type <> 'BULK' OR status IN ('AVAILABLE', 'RETIRED')",
            name="ck_inventory_items_bulk_status",
        ),
        CheckConstraint(
            "tracking_type <> 'BULK' OR current_holder_user_id IS NULL",
            name="ck_inventory_items_bulk_no_holder",
        ),
        CheckConstraint("stock_quantity >= 0", name="ck_inventory_items_stock_nonneg"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_items_reserved_nonneg"),
        CheckConstraint(
            "reserved_quantity <= stock_quantity", name="ck_inventory_items_reserved_le_stock"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    inventory_category_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_categories.id"), nullable=False
    )
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    current_holder_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    asset_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    tracking_type: Mapped[InventoryTrackingType] = mapped_column(
        Enum(
            InventoryTrackingType,
            name="ck_inventory_items_tracking_type",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(
            InventoryStatus,
            name="ck_inventory_items_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    condition: Mapped[InventoryCondition | None] = mapped_column(
        Enum(
            InventoryCondition,
            name="ck_inventory_items_condition",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )

    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    reserved_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    minimum_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(150), nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="inventory_items")
    inventory_category: Mapped["InventoryCategory"] = relationship(
        back_populates="inventory_items"
    )
    current_location: Mapped["Location | None"] = relationship(
        back_populates="inventory_items"
    )
    current_holder: Mapped["User | None"] = relationship(
        back_populates="held_inventory_items",
        foreign_keys=[current_holder_user_id],
    )
