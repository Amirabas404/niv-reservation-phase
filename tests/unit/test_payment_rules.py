from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.payment_rules import payment_deadline_passed, payment_reminder_due, refund_amount

UTC = ZoneInfo("UTC")


def test_refund_is_fifty_percent_of_verified_amount():
    assert refund_amount(259000, 50) == 129500


def test_unverified_payment_refunds_nothing():
    assert refund_amount(0, 50) == 0


def test_refund_rounds_down_to_whole_toman():
    assert refund_amount(1001, 50) == 500


def test_invalid_percent_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        refund_amount(100, 150)


def test_reminder_is_due_eight_hours_before_booking():
    start = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)
    assert payment_reminder_due(start - timedelta(hours=8), start, 8) is True
    assert payment_reminder_due(start - timedelta(hours=9), start, 8) is False


def test_deadline_passes_at_configured_hours_before_booking():
    start = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)
    assert payment_deadline_passed(start - timedelta(hours=7), start, 7) is True
    assert payment_deadline_passed(start - timedelta(hours=7, minutes=1), start, 7) is False
