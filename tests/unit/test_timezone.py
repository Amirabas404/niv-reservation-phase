from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.timezone import (
    ensure_aware,
    jalali_to_utc,
    to_jalali_str,
    to_local,
)

TEHRAN = ZoneInfo("Asia/Tehran")


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        ensure_aware(datetime(2026, 11, 9, 12, 0))


def test_utc_is_converted_to_tehran_local_time():
    # Iran has no DST since 2022: Tehran is UTC+03:30 year-round.
    utc_dt = datetime(2026, 11, 9, 9, 0, tzinfo=ZoneInfo("UTC"))
    local = to_local(utc_dt)
    assert (local.hour, local.minute) == (12, 30)


def test_jalali_round_trip():
    utc_dt = jalali_to_utc(1405, 7, 15, 10, 30)
    assert to_jalali_str(utc_dt) == "1405/07/15 10:30"


def test_jalali_date_only_format():
    utc_dt = jalali_to_utc(1405, 7, 15, 10, 30)
    assert to_jalali_str(utc_dt, with_time=False) == "1405/07/15"


def test_jalali_to_utc_returns_aware_utc():
    utc_dt = jalali_to_utc(1405, 7, 15, 10, 30)
    assert utc_dt.tzinfo is not None
    assert utc_dt.utcoffset().total_seconds() == 0
