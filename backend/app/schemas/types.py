from datetime import datetime, timezone
from typing import Annotated

from pydantic import BeforeValidator


def _as_utc(value: datetime | None) -> datetime | None:
    """Attach UTC tzinfo to a naive datetime read off an ORM object.

    Every system timestamp column in this schema is naive DATETIME2, whose
    numeric value represents UTC by convention (app.core.time.utc_now_naive
    is the sole write path) - see docs/TECH_DEBT.md's UTC timestamp
    normalization entry. This makes that convention explicit at the API
    boundary, so responses always carry a Z/+00:00 suffix and the frontend's
    existing `new Date(...)` calls parse them correctly instead of silently
    treating an unmarked string as the browser's local time.

    Only valid for rows written after that normalization migration - see
    the TECH_DEBT entry for why rows predating it remain of unproven basis
    until the separately-approved dev-database reseed happens.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


UTCDatetime = Annotated[datetime, BeforeValidator(_as_utc)]
