from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import TicketInventoryUsageStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.inventory_item import InventoryItem
    from app.models.ticket import Ticket
    from app.models.user import User


class TicketInventoryUsage(TimestampMixin, Base):
    """The CURRENT relationship between a ticket and an inventory item -
    not a history/audit log (that's InventoryTransaction, Milestone 12).

    A row exists only while its status is true: RESERVED (held against this
    ticket, not yet used) or CONSUMED (actually used to resolve this
    ticket). Releasing a reservation or undoing a consumption deletes the
    row entirely - there is nothing "current" left to represent once
    either happens. See TicketInventoryService for the full reserve/
    release/consume/remove state machine and the InventoryItem side effects
    (status/stock_quantity/reserved_quantity/current_holder_user_id) each
    transition applies.

    company_id is denormalized from the parent ticket, same convention as
    Comment/Attachment. The unique constraint on (ticket_id,
    inventory_item_id) both prevents a duplicate row for the same
    ticket+item pair and forces a second BULK reservation of an
    already-attached item to merge into the existing row's quantity
    instead (see TicketInventoryService.reserve).

    Known Version 1 limitation (intentional, approved as-is - not a bug):
    because at most one row may exist per (ticket_id, inventory_item_id),
    a BULK item can only ever be consumed once per ticket. Repeated
    reservations before consumption keep merging into the same RESERVED
    row as designed, but once that row is CONSUMED, the same item cannot
    be reserved again on that ticket until a Company Administrator first
    undoes the consumption (TicketInventoryService.remove) - there is no
    way to represent a second, independent consumption event of the same
    item on the same ticket while the first one still stands. A future
    version can lift this by tracking multiple consumption events per
    ticket+item, most naturally once InventoryTransaction (Milestone 12)
    provides the full event history this table deliberately doesn't.
    """

    __tablename__ = "ticket_inventory_usage"
    __table_args__ = (
        UniqueConstraint(
            "ticket_id", "inventory_item_id", name="uq_ticket_inventory_usage_ticket_item"
        ),
        CheckConstraint("quantity > 0", name="ck_ticket_inventory_usage_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[TicketInventoryUsageStatus] = mapped_column(
        Enum(
            TicketInventoryUsageStatus,
            name="ck_ticket_inventory_usage_status",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    selected_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    company: Mapped["Company"] = relationship()
    ticket: Mapped["Ticket"] = relationship(back_populates="inventory_usages")
    inventory_item: Mapped["InventoryItem"] = relationship()
    selected_by: Mapped["User"] = relationship()
