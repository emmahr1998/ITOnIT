from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAtMixin:
    """Adds a required, server-generated creation timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """Adds required creation and last-updated timestamps."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
