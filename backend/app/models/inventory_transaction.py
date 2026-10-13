from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import InventoryTransactionType
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.inventory_item import InventoryItem
    from app.models.ticket import Ticket
    from app.models.user import User


class InventoryTransaction(CreatedAtMixin, Base):
    """The permanent, append-only audit trail for InventoryItem changes -
    approved Phase 12.1 design (see the InventoryTransaction design doc).

    Unlike TicketInventoryUsage (the CURRENT ticket<->item relationship,
    which is deleted once it stops being true), a row here is never
    updated or deleted once written - CreatedAtMixin only (no updated_at),
    InventoryTransactionRepository overrides its inherited update()/
    delete() to raise, InventoryTransactionService exposes neither at
    all, and no route allows writing one directly. That is the
    append-only guarantee, enforced structurally rather than by
    convention.

    One business event = one row. quantity_delta's meaning is
    type-dependent rather than tied to one fixed InventoryItem column
    (stock_quantity vs. reserved_quantity) - see InventoryTransactionType's
    docstring and the services that call InventoryTransactionService.record
    for the exact mapping per event.

    ticket_id uses ON DELETE SET NULL, not this schema's usual NO ACTION:
    TicketService.delete_ticket hard-deletes ticket rows, and a NO ACTION
    FK here would make that delete fail the moment a transaction row
    references it. SET NULL lets the ticket disappear while the
    transaction row (and its human-readable ticket reference, permanently
    preserved in `notes` for the ticket-deletion-cleanup case) survives -
    mirrors InventoryItem.current_location_id/current_holder_user_id
    already using SET NULL for the identical "the referenced row may
    legitimately disappear" reason.

    company_id is denormalized from the parent item, same convention as
    Comment/Attachment/TicketInventoryUsage.
    """

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index(
            "ix_inventory_transactions_company_item_created",
            "company_id",
            "inventory_item_id",
            "created_at",
        ),
        Index(
            "ix_inventory_transactions_company_ticket",
            "company_id",
            "ticket_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id"), nullable=False
    )
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    performed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    transaction_type: Mapped[InventoryTransactionType] = mapped_column(
        Enum(
            InventoryTransactionType,
            name="ck_inventory_transactions_type",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    quantity_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship()
    inventory_item: Mapped["InventoryItem"] = relationship()
    ticket: Mapped["Ticket | None"] = relationship()
    performed_by: Mapped["User"] = relationship()
