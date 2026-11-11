from datetime import datetime, timedelta


def refund_amount(verified_paid: int, refund_percent: int) -> int:
    """Refund is a percentage of the VERIFIED amount, rounded down to whole Toman."""
    if not 0 <= refund_percent <= 100:
        raise ValueError("refund_percent must be between 0 and 100")
    if verified_paid <= 0:
        return 0
    return verified_paid * refund_percent // 100


def payment_reminder_due(now: datetime, booking_start: datetime, hours_before: int) -> bool:
    return now >= booking_start - timedelta(hours=hours_before)


def payment_deadline_passed(now: datetime, booking_start: datetime, hours_before: int) -> bool:
    return now >= booking_start - timedelta(hours=hours_before)
