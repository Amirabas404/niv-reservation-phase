from datetime import UTC, date, datetime, time

from bots.customer.formatting import (
    fa,
    jalali_date_label,
    local_start_utc,
    money,
    time_slots,
    upcoming_dates,
)


def test_persian_digits():
    assert fa(1405) == "۱۴۰۵"


def test_money_format():
    assert money(259000) == "۲۵۹,۰۰۰ تومان"


def test_jalali_date_label_contains_persian_month_and_weekday():
    label = jalali_date_label(date(2026, 11, 9))  # Monday
    assert label.startswith("دوشنبه")


def test_time_slots_start_and_end():
    slots = time_slots()
    assert slots[0] == "07:30"
    assert slots[-1] == "22:30"
    assert len(slots) == 31  # 07:30 .. 22:30 every 30 minutes


def test_upcoming_dates_includes_today_and_has_requested_length():
    days = upcoming_dates(date(2026, 11, 9), days=14)
    assert days[0] == date(2026, 11, 9)
    assert len(days) == 14


def test_local_start_is_converted_to_utc():
    # 14:00 Tehran (UTC+3:30, no DST) is 10:30 UTC
    utc = local_start_utc(date(2026, 11, 10), "14:00")
    assert utc.tzinfo is not None
    assert (utc.hour, utc.minute) == (10, 30)
