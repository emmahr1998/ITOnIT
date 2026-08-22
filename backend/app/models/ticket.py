from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import TicketStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.category import Category
    from app.models.comment import Comment
    from app.models.company import Company
    from app.models.location import Location
    from app.models.priority import Priority
    from app.models.ticket_history import TicketHistory
    from app.models.ticket_inventory_usage import TicketInventoryUsage
    from app.models.user import User


class Ticket(TimestampMixin, Base):
    """A single IT support request, tracked from submission through resolution.

    Company-owned: ticket_number is unique per company (each company's
    numbering starts from IT-{year}-000001 independently), not platform-wide.
    """

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("company_id", "ticket_number", name="uq_tickets_company_id_ticket_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(
            TicketStatus,
            name="ck_tickets_status",
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    priority_id: Mapped[int] = mapped_column(ForeignKey("priorities.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    assigned_technician_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # No default/server_default - these are only ever set by TicketService
    # on the specific NEW->RESOLVED/CLOSED transition (see change_status),
    # via app.core.time.utc_now_naive, same UTC contract as every other
    # timestamp in this schema. See docs/TECH_DEBT.md's UTC timestamp
    # normalization entry.
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="tickets")
    category: Mapped["Category"] = relationship(back_populates="tickets")
    priority: Mapped["Priority"] = relationship(back_populates="tickets")
    location: Mapped["Location | None"] = relationship(back_populates="tickets")
    created_by: Mapped["User"] = relationship(
        back_populates="created_tickets", foreign_keys=[created_by_user_id]
    )
    assigned_technician: Mapped["User | None"] = relationship(
        back_populates="assigned_tickets", foreign_keys=[assigned_technician_id]
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    history: Mapped[list["TicketHistory"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    inventory_usages: Mapped[list["TicketInventoryUsage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
