from app.core.fa import fa, money
from app.services.report_text import format_daily


def test_money_uses_persian_digits():
    assert money(259000) == "۲۵۹,۰۰۰ تومان"
    assert money(None) == "—"


def test_fa_digits():
    assert fa(2026) == "۲۰۲۶"


def test_daily_text_contains_key_figures():
    report = {
        "date_jalali": "1405/08/18",
        "requested_today": 4, "confirmed": 2, "rejected": 1, "cancelled": 0, "pending": 3,
        "payments": {"verified": 1}, "verified_amount": 259000, "guests_total": 12,
        "spaces": {"hall": {"name": "سالن پایین", "reservations": 2, "guests": 8}},
        "tables": {"total": 38, "blocked": 1, "capacity_not_set": 30},
    }
    text = format_daily(report)
    assert "۱۴۰۵/۰۸/۱۸" not in text  # date string is passed through as-is
    assert "1405/08/18" in text
    assert "۲۵۹,۰۰۰ تومان" in text
    assert "سالن پایین" in text
