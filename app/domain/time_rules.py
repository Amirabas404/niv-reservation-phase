"""Time rules. All functions are pure; callers pass timezone-aware datetimes."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.domain.errors import DesignLeadTimeError, TimeRuleError


@dataclass(frozen=True)
class RulesConfig:
    dine_in_open: time
    dine_in_close: time
    design_min_lead_hours: int
    cancellation_cutoff_hours: int
    reservation_duration_minutes: int
    payment_reminder_hours_before: int
    payment_deadline_hours_before: int
    refund_percent: int


def validate_dine_in_start(booking_local: datetime, now_local: datetime, rules: RulesConfig) -> None:
    """Dine-in reservations must be in the future and inside [open, close)."""
    if booking_local <= now_local:
        raise TimeRuleError("زمان رزرو باید در آینده باشد.")
    t = booking_local.time()
    if not (rules.dine_in_open <= t < rules.dine_in_close):
        raise TimeRuleError(
            "ساعت انتخابی خارج از ساعت پذیرایی داخل مجموعه است. "
            f"پذیرایی از {rules.dine_in_open.strftime('%H:%M')} تا {rules.dine_in_close.strftime('%H:%M')} انجام می‌شود."
        )


def check_design_lead_time(requested_at: datetime, booking_start: datetime, rules: RulesConfig) -> None:
    """Design bookings need at least N hours between submission and the booking time."""
    if booking_start - requested_at < timedelta(hours=rules.design_min_lead_hours):
        raise DesignLeadTimeError(
            f"رزرو دیزاین فقط در صورتی امکان‌پذیر است که حداقل {rules.design_min_lead_hours} ساعت "
            "قبل از زمان مدنظر ثبت شود. می‌توانید برای بررسی به پشتیبانی متصل شوید."
        )


def can_cancel_self_service(now: datetime, booking_start: datetime, rules: RulesConfig) -> bool:
    return booking_start - now >= timedelta(hours=rules.cancellation_cutoff_hours)
