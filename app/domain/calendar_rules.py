"""Calendar helpers for reports. Pure functions; boundaries are computed in the venue timezone."""

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    return start.astimezone(ZoneInfo("UTC")), (start + timedelta(days=1)).astimezone(ZoneInfo("UTC"))


def month_bounds_utc(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=tz)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = datetime(next_year, next_month, 1, tzinfo=tz)
    return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))


def is_last_day_of_month(day: date) -> bool:
    return day.day == calendar.monthrange(day.year, day.month)[1]


def parse_year_month(value: str) -> tuple[int, int]:
    year_s, month_s = value.split("-")
    year, month = int(year_s), int(month_s)
    if not 1 <= month <= 12 or not 2000 <= year <= 2100:
        raise ValueError("invalid year-month")
    return year, month
