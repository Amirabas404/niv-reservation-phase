"""Pure helpers for the customer bot: Persian digits, Jalali labels, time slots.

Deliberately free of Telegram and database imports so it can be unit tested.
"""

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import jdatetime

TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tehran"))
UTC = ZoneInfo("UTC")

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
# Index matches Python's date.weekday(): Monday = 0
WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]

SPACE_NAMES = {
    "hall": "سالن پایین",
    "roof_family": "روف‌گاردن خانوادگی",
    "roof_smoke_free": "روف‌گاردن فری اسموک",
    "vip": "VIP",
}
DESIGN_NAMES = {
    "none": "بدون دیزاین",
    "dried_flower_candle": "گل خشک و شمع",
    "balloon_stand": "استند بادکنک",
    "both": "گل خشک، شمع و استند بادکنک",
}
STATUS_NAMES = {
    "pending_manager_approval": "در انتظار تأیید مجموعه",
    "awaiting_payment": "در انتظار پرداخت",
    "receipt_submitted": "رسید ارسال شد، در انتظار بررسی",
    "confirmed": "تأیید شده ✅",
    "rejected": "رد شده",
    "rejected_unpaid": "رد شده (عدم پرداخت)",
    "cancelled": "لغوشده",
}


def fa(value: object) -> str:
    return str(value).translate(_FA_DIGITS)


def money(amount: int) -> str:
    return f"{fa(f'{amount:,}')} تومان"


def jalali_date_label(d: date) -> str:
    j = jdatetime.date.fromgregorian(year=d.year, month=d.month, day=d.day)
    return f"{WEEKDAYS[d.weekday()]} {fa(j.day)} {JALALI_MONTHS[j.month - 1]}"


def jalali_datetime_label(utc_dt: datetime) -> str:
    local = utc_dt.astimezone(TZ)
    j = jdatetime.date.fromgregorian(year=local.year, month=local.month, day=local.day)
    clock = local.strftime("%H:%M")
    return f"{fa(j.year)}/{fa(f'{j.month:02d}')}/{fa(f'{j.day:02d}')} ساعت {fa(clock)}"


def upcoming_dates(today: date, days: int = 14) -> list[date]:
    return [today + timedelta(days=i) for i in range(days)]


def time_slots(start: time = time(7, 30), last: time = time(22, 30), step_minutes: int = 30) -> list[str]:
    """Selectable start times. The Backend remains the authority for validation.

    Step size is an assumption (30 minutes) to confirm with the owner.
    """
    out: list[str] = []
    cursor = datetime(2000, 1, 1, start.hour, start.minute)
    end = datetime(2000, 1, 1, last.hour, last.minute)
    while cursor <= end:
        out.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=step_minutes)
    return out


def local_start_utc(d: date, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ).astimezone(UTC)
