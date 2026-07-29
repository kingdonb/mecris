"""
TimezoneService — Single source of truth for US/Eastern timezone operations.

All daily-boundary logic (Beeminder daystamps, walk aggregation, language rollover)
must use this service. Never use zoneinfo/ZoneId directly in business logic.
"""
import zoneinfo
from datetime import datetime, date, timezone

EASTERN = zoneinfo.ZoneInfo("America/New_York")


def now_eastern() -> datetime:
    """Current time in US/Eastern (aware)."""
    return datetime.now(EASTERN)


def today_eastern() -> date:
    """Current date in US/Eastern."""
    return now_eastern().date()


def day_start_eastern(d: date = None) -> datetime:
    """
    Midnight start of given Eastern date (aware, tz=EASTERN).
    Defaults to today in Eastern.
    """
    if d is None:
        d = today_eastern()
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=EASTERN)


def day_end_eastern(d: date = None) -> datetime:
    """
    End of given Eastern date (23:59:59.999999, aware, tz=EASTERN).
    Defaults to today in Eastern.
    """
    if d is None:
        d = today_eastern()
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=EASTERN)


def daystamp(dt: datetime) -> str:
    """
    Beeminder daystamp (YYYYMMDD) for given datetime.
    Converts to Eastern first, then formats.
    Naive datetimes treated as Eastern (local timezone).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EASTERN)
    return dt.astimezone(EASTERN).strftime("%Y%m%d")


def to_eastern(dt: datetime) -> datetime:
    """Convert any aware datetime to Eastern. Naive treated as Eastern."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=EASTERN)
    return dt.astimezone(EASTERN)


def eastern_midnight_utc(d: date) -> datetime:
    """
    Eastern midnight for given date, expressed in UTC (aware, tz=UTC).
    Useful for DB queries that store UTC.
    """
    eastern_midnight = day_start_eastern(d)
    return eastern_midnight.astimezone(timezone.utc)


def is_today_eastern(dt: datetime) -> bool:
    """Check if datetime falls on today's Eastern date."""
    return to_eastern(dt).date() == today_eastern()