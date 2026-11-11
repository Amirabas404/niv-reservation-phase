"""Timezone and Jalali (Persian calendar) helpers.

Storage rule: datetimes are stored as timezone-aware UTC (timestamptz).
Display rule: converted to the configured timezone and shown as Jalali.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime

from app.core.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def utc_now() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Naive datetime is not allowed; attach a timezone first.")
    return dt


def to_local(dt: datetime) -> datetime:
    return ensure_aware(dt).astimezone(local_tz())


def to_jalali_str(dt: datetime, with_time: bool = True) -> str:
    local = to_local(dt).replace(tzinfo=None)
    j = jdatetime.datetime.fromgregorian(
        year=local.year,
        month=local.month,
        day=local.day,
        hour=local.hour,
        minute=local.minute,
    )
    return j.strftime("%Y/%m/%d %H:%M") if with_time else j.strftime("%Y/%m/%d")


def jalali_to_utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Convert a Jalali wall-clock time in the configured timezone to aware UTC."""
    j = jdatetime.datetime(year, month, day, hour, minute)
    local_naive = j.togregorian()
    return local_naive.replace(tzinfo=local_tz()).astimezone(ZoneInfo("UTC"))
