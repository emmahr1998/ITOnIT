from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """The one function that generates every persisted system timestamp in
    this app (CreatedAtMixin/TimestampMixin defaults, Ticket.resolved_at/
    closed_at, Comment.updated_at).

    Returns a naive datetime whose numeric value represents UTC - not an
    aware one - because SQL Server's DATETIME/DATETIME2 types cannot store
    timezone information at all (confirmed empirically: an aware value
    round-trips through pyodbc byte-identical to a naive one, and every
    value reads back with tzinfo=None regardless of what was written). The
    persistence contract is a documented convention enforced by always
    going through this function, not something the column type enforces -
    see docs/TECH_DEBT.md's UTC timestamp normalization entry.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
