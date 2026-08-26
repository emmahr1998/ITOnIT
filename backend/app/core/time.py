from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


class InvalidCompanyTimezoneError(Exception):
    """Raised when Company.timezone is not a valid IANA timezone name.

    Deliberately not silently corrected to UTC - a company's timezone
    being wrong is a real data problem (matches this codebase's existing
    philosophy on get_current_company_id: failing loudly is a clearer
    signal than quietly falling back and misrepresenting a company's own
    reporting boundaries). Callers decide how to surface this (a 400/500
    at the route layer, once one exists) - this module only refuses to
    guess.
    """

    def __init__(self, timezone_name: str) -> None:
        super().__init__(f"Invalid company timezone: {timezone_name!r}")
        self.timezone_name = timezone_name


def resolve_company_zone(timezone_name: str) -> ZoneInfo:
    """The one place a company's stored timezone string becomes a real
    IANA zone, or fails loudly. Every company in this system is seeded
    with 'UTC' today (see docs/TECH_DEBT.md's UTC timestamp normalization
    entry) and the field isn't yet editable anywhere, so this always
    succeeds in practice - it exists so future editable-timezone support
    doesn't have to revisit the reporting-boundary math, only this one
    validation point.
    """
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidCompanyTimezoneError(timezone_name) from exc


def local_day_boundaries_utc(
    timezone_name: str, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """[start_of_local_day, start_of_next_local_day) for "today" in the
    company's own timezone, returned as naive UTC datetimes - matching
    this schema's naive-UTC storage contract (see utc_now_naive), so the
    result compares directly against created_at/resolved_at with no
    further conversion needed at the call site.

    `now` is only for tests - production callers always use the real
    current instant.
    """
    zone = resolve_company_zone(timezone_name)
    reference = now if now is not None else datetime.now(timezone.utc)
    local_now = reference.astimezone(zone)
    local_midnight = datetime(
        local_now.year, local_now.month, local_now.day, tzinfo=zone
    )
    next_local_midnight = local_midnight + timedelta(days=1)
    return (
        local_midnight.astimezone(timezone.utc).replace(tzinfo=None),
        next_local_midnight.astimezone(timezone.utc).replace(tzinfo=None),
    )


def local_month_boundaries_utc(
    timezone_name: str, num_months: int, *, now: datetime | None = None
) -> list[tuple[str, datetime, datetime]]:
    """The `num_months` most recent calendar months in the company's own
    timezone, oldest first, including the current month. Each entry is
    (label, start_utc, end_utc) - label is "YYYY-MM" in the company's
    local calendar; start/end are naive UTC datetimes, same rationale as
    local_day_boundaries_utc.

    Computing each month's boundary via datetime(year, month, 1,
    tzinfo=zone) rather than naive arithmetic on a single "now" value
    means DST transitions within the window are handled correctly by
    zoneinfo itself (PEP 495), not approximated.
    """
    if num_months < 1:
        raise ValueError("num_months must be at least 1")

    zone = resolve_company_zone(timezone_name)
    reference = now if now is not None else datetime.now(timezone.utc)
    local_now = reference.astimezone(zone)

    year, month = local_now.year, local_now.month
    year_months: list[tuple[int, int]] = []
    for _ in range(num_months):
        year_months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    year_months.reverse()

    boundaries: list[tuple[str, datetime, datetime]] = []
    for y, m in year_months:
        start_local = datetime(y, m, 1, tzinfo=zone)
        next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
        end_local = datetime(next_y, next_m, 1, tzinfo=zone)
        boundaries.append(
            (
                f"{y:04d}-{m:02d}",
                start_local.astimezone(timezone.utc).replace(tzinfo=None),
                end_local.astimezone(timezone.utc).replace(tzinfo=None),
            )
        )
    return boundaries
