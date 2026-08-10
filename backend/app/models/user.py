from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.comment import Comment
    from app.models.company import Company
    from app.models.department import Department
    from app.models.inventory_item import InventoryItem
    from app.models.role import Role
    from app.models.ticket import Ticket
    from app.models.ticket_history import TicketHistory


class User(TimestampMixin, Base):
    """A person who interacts with the system: employee, technician, company
    administrator, or (for exactly one row, platform-wide) system administrator.

    company_id is nullable only for the single System Administrator account,
    which belongs to ITOnIT itself rather than to any customer company - every
    other role always has a company_id. username and email are unique per
    company, not platform-wide: the login flow resolves the company (via
    company_code) before looking a user up, so the same email may exist in
    two different companies without ambiguity.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("company_id", "username", name="uq_users_company_id_username"),
        UniqueConstraint("company_id", "email", name="uq_users_company_id_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    theme: Mapped[str | None] = mapped_column(String(20), nullable=True, default="light")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    company: Mapped["Company | None"] = relationship(back_populates="users")
    role: Mapped["Role"] = relationship(back_populates="users")
    department: Mapped["Department | None"] = relationship(back_populates="users")

    created_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="created_by",
        foreign_keys="Ticket.created_by_user_id",
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="assigned_technician",
        foreign_keys="Ticket.assigned_technician_id",
    )
    comments: Mapped[list["Comment"]] = relationship(back_populates="author")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="uploaded_by")
    history_entries: Mapped[list["TicketHistory"]] = relationship(
        back_populates="changed_by"
    )
    # passive_deletes=True: trust the DB's own ON DELETE SET NULL (see
    # InventoryItem.current_holder_user_id) instead of SQLAlchemy trying to
    # load and null these out in Python first.
    held_inventory_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="current_holder",
        foreign_keys="InventoryItem.current_holder_user_id",
        passive_deletes=True,
    )
