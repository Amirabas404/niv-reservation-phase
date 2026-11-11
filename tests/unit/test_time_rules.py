from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.errors import DesignLeadTimeError, TimeRuleError
from app.domain.time_rules import (
    RulesConfig,
    can_cancel_self_service,
    check_design_lead_time,
    validate_dine_in_start,
)

TEHRAN = ZoneInfo("Asia/Tehran")
UTC = ZoneInfo("UTC")
RULES = RulesConfig(
    dine_in_open=time(7, 30),
    dine_in_close=time(23, 30),
    design_min_lead_hours=5,
    cancellation_cutoff_hours=8,
    reservation_duration_minutes=120,
    payment_reminder_hours_before=8,
    payment_deadline_hours_before=7,
    refund_percent=50,
)
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=TEHRAN)


def test_open_boundary_is_allowed():
    validate_dine_in_start(datetime(2026, 11, 10, 7, 30, tzinfo=TEHRAN), NOW, RULES)


def test_last_minute_before_close_is_allowed():
    validate_dine_in_start(datetime(2026, 11, 10, 23, 29, tzinfo=TEHRAN), NOW, RULES)


def test_close_boundary_is_rejected():
    with pytest.raises(TimeRuleError):
        validate_dine_in_start(datetime(2026, 11, 10, 23, 30, tzinfo=TEHRAN), NOW, RULES)


def test_before_open_is_rejected():
    with pytest.raises(TimeRuleError):
        validate_dine_in_start(datetime(2026, 11, 10, 7, 29, tzinfo=TEHRAN), NOW, RULES)


def test_past_time_is_rejected():
    with pytest.raises(TimeRuleError):
        validate_dine_in_start(datetime(2026, 11, 9, 7, 45, tzinfo=TEHRAN), NOW, RULES)


def test_design_three_hours_ahead_is_rejected_with_support_offer():
    requested = datetime(2026, 11, 10, 14, 0, tzinfo=TEHRAN)
    booking = datetime(2026, 11, 10, 17, 0, tzinfo=TEHRAN)
    with pytest.raises(DesignLeadTimeError) as exc:
        check_design_lead_time(requested, booking, RULES)
    assert exc.value.support_offer is True


def test_design_exactly_five_hours_ahead_is_allowed():
    requested = datetime(2026, 11, 10, 14, 0, tzinfo=TEHRAN)
    booking = datetime(2026, 11, 10, 19, 0, tzinfo=TEHRAN)
    check_design_lead_time(requested, booking, RULES)


def test_lead_time_is_measured_across_timezones():
    requested = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    booking = datetime(2026, 11, 10, 14, 0, tzinfo=TEHRAN)  # 10:30 UTC -> 1.5h
    with pytest.raises(DesignLeadTimeError):
        check_design_lead_time(requested, booking, RULES)


def test_cancellation_exactly_eight_hours_ahead_is_allowed():
    booking = NOW + timedelta(hours=8)
    assert can_cancel_self_service(NOW, booking, RULES) is True


def test_cancellation_inside_cutoff_needs_support():
    booking = NOW + timedelta(hours=7, minutes=59)
    assert can_cancel_self_service(NOW, booking, RULES) is False
