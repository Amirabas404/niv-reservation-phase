"""Validation for manager-editable settings. Invalid values never reach the database."""

import re
from datetime import time

from app.domain.errors import DomainError

_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
PRICING_SPACE_KEYS = ("hall", "roof_family", "roof_smoke_free")
PRICING_DESIGN_KEYS = ("dried_flower_candle", "balloon_stand", "both")


def _int_in(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainError(f"«{name}» باید عدد صحیح باشد.")
    if not low <= value <= high:
        raise DomainError(f"«{name}» باید بین {low} و {high} باشد.")
    return value


def _hhmm(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HHMM.fullmatch(value):
        raise DomainError(f"«{name}» باید به شکل HH:MM باشد.")
    return value


def _require_keys(value: object, keys: tuple[str, ...], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise DomainError(f"ساختار «{name}» معتبر نیست.")
    return value


def validate_setting(key: str, value: object) -> object:
    if key == "pricing":
        if not isinstance(value, dict):
            raise DomainError("ساختار قیمت‌ها معتبر نیست.")
        expected_keys = (
            "per_person", "vip_flat_up_to_4", "vip_flat_5_to_10",
            "vip_max_party", "designs", "catering_per_person",
        )
        _require_keys(value, expected_keys, "pricing")
        per_person = _require_keys(value["per_person"], PRICING_SPACE_KEYS, "per_person")
        designs = _require_keys(value["designs"], PRICING_DESIGN_KEYS, "designs")
        for k, v in per_person.items():
            _int_in(v, f"قیمت نفری {k}", 0, 100_000_000)
        for k, v in designs.items():
            _int_in(v, f"قیمت دیزاین {k}", 0, 100_000_000)
        _int_in(value["vip_flat_up_to_4"], "VIP ۱ تا ۴ نفر", 0, 100_000_000)
        _int_in(value["vip_flat_5_to_10"], "VIP ۵ تا ۱۰ نفر", 0, 100_000_000)
        _int_in(value["vip_max_party"], "حداکثر نفرات VIP", 1, 50)
        _int_in(value["catering_per_person"], "هزینه پذیرایی نفری", 0, 100_000_000)
        return value

    if key == "rules":
        if not isinstance(value, dict):
            raise DomainError("ساختار قوانین معتبر نیست.")
        open_t = _hhmm(value.get("dine_in_open"), "شروع پذیرایی")
        close_t = _hhmm(value.get("dine_in_close"), "پایان پذیرایی")
        if time.fromisoformat(open_t) >= time.fromisoformat(close_t):
            raise DomainError("ساعت شروع باید قبل از ساعت پایان باشد.")
        _int_in(value.get("design_min_lead_hours"), "حداقل فاصله دیزاین (ساعت)", 0, 72)
        _int_in(value.get("cancellation_cutoff_hours"), "مهلت لغو (ساعت)", 0, 168)
        _int_in(value.get("reservation_duration_minutes"), "مدت رزرو (دقیقه)", 30, 480)
        _int_in(value.get("payment_reminder_hours_before"), "یادآوری پرداخت (ساعت)", 1, 72)
        _int_in(value.get("payment_deadline_hours_before"), "مهلت پرداخت (ساعت)", 1, 72)
        _int_in(value.get("refund_percent"), "درصد استرداد", 0, 100)
        return value

    if key == "reports":
        if not isinstance(value, dict):
            raise DomainError("ساختار گزارش‌ها معتبر نیست.")
        _hhmm(value.get("nightly_time"), "زمان گزارش شبانه")
        _hhmm(value.get("monthly_time"), "زمان گزارش ماهانه")
        return value

    if key == "bank_card":
        if not isinstance(value, dict):
            raise DomainError("ساختار اطلاعات کارت معتبر نیست.")
        card = str(value.get("card_number", ""))
        if not re.fullmatch(r"\d{16}", card):
            raise DomainError("شماره کارت باید ۱۶ رقم باشد.")
        owner = str(value.get("owner_name", "")).strip()
        if len(owner) < 2:
            raise DomainError("نام صاحب کارت معتبر نیست.")
        return {"card_number": card, "owner_name": owner}

    raise DomainError("این تنظیم قابل ویرایش نیست.")
