from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain.calendar_rules import day_bounds_utc, is_last_day_of_month, month_bounds_utc, parse_year_month

TEHRAN = ZoneInfo("Asia/Tehran")
UTC = ZoneInfo("UTC")


def test_day_bounds_are_local_midnight_in_utc():
    start, end = day_bounds_utc(date(2026, 11, 9), TEHRAN)
    assert start == datetime(2026, 11, 9, 0, 0, tzinfo=TEHRAN).astimezone(UTC)
    assert (end - start).total_seconds() == 24 * 3600


def test_month_bounds_handle_december_rollover():
    start, end = month_bounds_utc(2026, 12, TEHRAN)
    assert end == datetime(2027, 1, 1, tzinfo=TEHRAN).astimezone(UTC)


def test_last_day_detection():
    assert is_last_day_of_month(date(2026, 11, 30)) is True
    assert is_last_day_of_month(date(2026, 11, 29)) is False
    assert is_last_day_of_month(date(2028, 2, 29)) is True


def test_parse_year_month_rejects_bad_month():
    assert parse_year_month("2026-11") == (2026, 11)
    with pytest.raises(ValueError):
        parse_year_month("2026-13")
