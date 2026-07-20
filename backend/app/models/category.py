from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Category(CreatedAtMixin, Base):
    """Classifies tickets by the type of issue being reported (e.g. Hardware, Network)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category")
