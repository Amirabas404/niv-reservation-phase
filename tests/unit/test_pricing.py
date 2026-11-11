import pytest

from app.domain.errors import PricingError
from app.domain.pricing import DesignCode, PricingConfig, SpaceCode, compute_quote

CFG = PricingConfig(
    per_person={"hall": 39000, "roof_family": 39000, "roof_smoke_free": 39000},
    vip_flat_up_to_4=259000,
    vip_flat_5_to_10=390000,
    vip_max_party=10,
    designs={"dried_flower_candle": 259000, "balloon_stand": 129000, "both": 388000},
    catering_per_person=39000,
)


def test_hall_is_priced_per_person():
    q = compute_quote(CFG, SpaceCode.HALL, 3)
    assert q.space_amount == 117000
    assert q.total == 117000


def test_vip_four_people_is_flat_259000():
    assert compute_quote(CFG, SpaceCode.VIP, 4).total == 259000


def test_vip_eight_people_is_flat_390000_not_multiplied():
    q = compute_quote(CFG, SpaceCode.VIP, 8)
    assert q.total == 390000


def test_vip_above_ten_is_rejected():
    with pytest.raises(PricingError):
        compute_quote(CFG, SpaceCode.VIP, 11)


def test_both_designs_cost_388000_and_are_not_added_twice():
    q = compute_quote(CFG, SpaceCode.ROOF_FAMILY, 2, DesignCode.BOTH)
    assert q.design_amount == 388000
    assert q.total == 78000 + 388000


def test_design_price_does_not_depend_on_party_size():
    small = compute_quote(CFG, SpaceCode.HALL, 2, DesignCode.BALLOON_STAND).design_amount
    large = compute_quote(CFG, SpaceCode.HALL, 9, DesignCode.BALLOON_STAND).design_amount
    assert small == large == 129000


def test_catering_is_per_person_on_whole_party():
    q = compute_quote(CFG, SpaceCode.HALL, 8, with_cake=True)
    assert q.catering_amount == 8 * 39000
    assert q.total == 8 * 39000 + 8 * 39000


def test_no_design_and_no_cake_has_single_line_item():
    q = compute_quote(CFG, SpaceCode.HALL, 1)
    assert [i.code for i in q.items] == ["space"]


def test_zero_party_is_rejected():
    with pytest.raises(PricingError):
        compute_quote(CFG, SpaceCode.HALL, 0)


def test_snapshot_contains_total_and_items():
    snap = compute_quote(CFG, SpaceCode.HALL, 2, DesignCode.BOTH, with_cake=True).to_snapshot()
    assert snap["total"] == 78000 + 388000 + 78000
    assert len(snap["items"]) == 3
