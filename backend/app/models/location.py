from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Location(TimestampMixin, Base):
    """A predefined physical location a ticket can be reported from
    (e.g. "Head Office - Floor 2 - Desk 18"), chosen from a list rather
    than typed freely.

    Retired locations are deactivated (is_active=False), never deleted -
    a ticket that already references one must keep a valid, meaningful
    location even after an admin retires it from the selectable list.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="location")
