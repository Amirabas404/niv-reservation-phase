import copy

import pytest

from app.domain.errors import DomainError
from app.domain.settings_validation import validate_setting

PRICING = {
    "per_person": {"hall": 39000, "roof_family": 39000, "roof_smoke_free": 39000},
    "vip_flat_up_to_4": 259000,
    "vip_flat_5_to_10": 390000,
    "vip_max_party": 10,
    "designs": {"dried_flower_candle": 259000, "balloon_stand": 129000, "both": 388000},
    "catering_per_person": 39000,
}
RULES = {
    "dine_in_open": "07:30", "dine_in_close": "23:30",
    "design_min_lead_hours": 5, "cancellation_cutoff_hours": 8,
    "reservation_duration_minutes": 120, "payment_reminder_hours_before": 8,
    "payment_deadline_hours_before": 7, "refund_percent": 50,
}


def test_valid_pricing_passes():
    assert validate_setting("pricing", PRICING) == PRICING


def test_negative_price_is_rejected():
    bad = copy.deepcopy(PRICING)
    bad["per_person"]["hall"] = -1
    with pytest.raises(DomainError):
        validate_setting("pricing", bad)


def test_boolean_is_not_a_price():
    bad = copy.deepcopy(PRICING)
    bad["catering_per_person"] = True
    with pytest.raises(DomainError):
        validate_setting("pricing", bad)


def test_missing_pricing_key_is_rejected():
    bad = copy.deepcopy(PRICING)
    del bad["designs"]["both"]
    with pytest.raises(DomainError):
        validate_setting("pricing", bad)


def test_rules_open_must_be_before_close():
    bad = copy.deepcopy(RULES)
    bad["dine_in_open"] = "23:30"
    with pytest.raises(DomainError):
        validate_setting("rules", bad)


def test_refund_percent_bounds():
    bad = copy.deepcopy(RULES)
    bad["refund_percent"] = 150
    with pytest.raises(DomainError):
        validate_setting("rules", bad)


def test_card_number_must_be_16_digits():
    with pytest.raises(DomainError):
        validate_setting("bank_card", {"card_number": "123", "owner_name": "سام مهاجر"})


def test_unknown_key_is_rejected():
    with pytest.raises(DomainError):
        validate_setting("secrets", {"x": 1})
