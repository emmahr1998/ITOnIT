from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.comment import Comment
    from app.models.department import Department
    from app.models.role import Role
    from app.models.ticket import Ticket
    from app.models.ticket_history import TicketHistory


class User(TimestampMixin, Base):
    """A person who interacts with the system: employee, technician, manager, or administrator."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
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
