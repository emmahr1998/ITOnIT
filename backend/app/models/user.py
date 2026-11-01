from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
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

    The single System Administrator belongs to the dedicated platform
    company (Company.is_platform) and is the only row with
    is_system_administrator=True - uq_users_single_system_administrator, a
    filtered unique index, makes a second one impossible at the database
    level. Platform access requires the flag, the System Administrator
    role, AND membership of the platform company together (see
    app.dependencies.auth.require_system_administrator), so any drift
    between them fails closed. company_id is still nullable in the schema
    for backward compatibility with the pre-platform-company layout, but
    after the add_platform_company migration no row has it null.
    username and email are unique per company, not platform-wide: the login
    flow resolves the company (via company_code) before looking a user up,
    so the same email may exist in two different companies without
    ambiguity.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("company_id", "username", name="uq_users_company_id_username"),
        UniqueConstraint("company_id", "email", name="uq_users_company_id_email"),
        Index(
            "uq_users_single_system_administrator",
            "is_system_administrator",
            unique=True,
            mssql_where=text("is_system_administrator = 1"),
            sqlite_where=text("is_system_administrator = 1"),
        ),
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
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    is_system_administrator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
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
