from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive

# DATETIME2(3) - millisecond precision, matches what DATETIME already
# offered in practice while giving exact (non-rounded) storage and being
# Microsoft's own recommended replacement for the legacy DATETIME type. See
# docs/TECH_DEBT.md's UTC timestamp normalization entry for why every
# column here changed type and default alongside this mixin.
_TIMESTAMP_TYPE = DATETIME2(precision=3)


class CreatedAtMixin:
    """Adds a required creation timestamp.

    Generated in Python as naive UTC (see app.core.time.utc_now_naive) -
    this is the sole write mechanism the application relies on.
    server_default=SYSUTCDATETIME() exists only as a defense-in-depth
    fallback for a write path that bypasses the ORM entirely (raw SQL,
    future bulk-load scripts); it is never expected to fire for normal
    application traffic, since SQLAlchemy always supplies the Python-side
    default value in the INSERT.
    """

    created_at: Mapped[datetime] = mapped_column(
        _TIMESTAMP_TYPE,
        default=utc_now_naive,
        server_default=text("SYSUTCDATETIME()"),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin):
    """Adds required creation and last-updated timestamps - see
    CreatedAtMixin's docstring for the UTC generation/fallback rationale,
    which applies identically to updated_at."""

    updated_at: Mapped[datetime] = mapped_column(
        _TIMESTAMP_TYPE,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        server_default=text("SYSUTCDATETIME()"),
        nullable=False,
    )
