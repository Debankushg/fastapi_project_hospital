from datetime import date, datetime, timedelta, timezone


def each_date(start: date, end: date) -> list[date]:
    """Every date from start to end inclusive."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def weekday_of(d: date) -> int:
    """0 = Sunday … 6 = Saturday (like JS getUTCDay)."""
    return (d.weekday() + 1) % 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def last_day_of(month: str) -> date:
    """Last date of a YYYY-MM month."""
    y, m = map(int, month.split("-"))
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
