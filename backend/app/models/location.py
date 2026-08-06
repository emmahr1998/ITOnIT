from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.ticket import Ticket


class Location(TimestampMixin, Base):
    """A predefined physical location a ticket can be reported from
    (e.g. "Head Office - Floor 2 - Desk 18"), chosen from a list rather
    than typed freely.

    Company-owned: title is unique per company. A default "Head Office"
    location is seeded for every new company at registration.

    Retired locations are deactivated (is_active=False), never deleted -
    a ticket that already references one must keep a valid, meaningful
    location even after an admin retires it from the selectable list.
    """

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("company_id", "title", name="uq_locations_company_id_title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    company: Mapped["Company"] = relationship(back_populates="locations")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="location")
