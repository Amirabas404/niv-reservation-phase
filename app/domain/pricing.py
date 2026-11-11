"""Pure pricing engine. All amounts are integers in Toman. No I/O.

The config comes from SystemSettings (manager-editable); this module only computes.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import PricingError


class SpaceCode(StrEnum):
    HALL = "hall"
    ROOF_FAMILY = "roof_family"
    ROOF_SMOKE_FREE = "roof_smoke_free"
    VIP = "vip"


class DesignCode(StrEnum):
    NONE = "none"
    DRIED_FLOWER_CANDLE = "dried_flower_candle"
    BALLOON_STAND = "balloon_stand"
    BOTH = "both"


SPACE_LABELS = {
    SpaceCode.HALL: "سالن پایین",
    SpaceCode.ROOF_FAMILY: "روف‌گاردن خانوادگی",
    SpaceCode.ROOF_SMOKE_FREE: "روف‌گاردن فری اسموک",
}

DESIGN_LABELS = {
    DesignCode.DRIED_FLOWER_CANDLE: "دیزاین گل خشک و شمع",
    DesignCode.BALLOON_STAND: "دیزاین استند بادکنک",
    DesignCode.BOTH: "دیزاین گل خشک، شمع و استند بادکنک",
}


@dataclass(frozen=True)
class PricingConfig:
    per_person: dict[str, int]
    vip_flat_up_to_4: int
    vip_flat_5_to_10: int
    vip_max_party: int
    designs: dict[str, int]
    catering_per_person: int


@dataclass(frozen=True)
class LineItem:
    code: str
    label: str
    quantity: int
    unit_amount: int
    total: int


@dataclass(frozen=True)
class Quote:
    items: tuple[LineItem, ...]
    space_amount: int
    design_amount: int
    catering_amount: int
    total: int

    def to_snapshot(self) -> dict:
        return {
            "currency": "TOMAN",
            "items": [
                {
                    "code": i.code,
                    "label": i.label,
                    "quantity": i.quantity,
                    "unit_amount": i.unit_amount,
                    "total": i.total,
                }
                for i in self.items
            ],
            "space_amount": self.space_amount,
            "design_amount": self.design_amount,
            "catering_amount": self.catering_amount,
            "total": self.total,
        }


def compute_quote(
    cfg: PricingConfig,
    space: SpaceCode | str,
    party_size: int,
    design: DesignCode | str = DesignCode.NONE,
    with_cake: bool = False,
) -> Quote:
    space = SpaceCode(space)
    design = DesignCode(design)

    if party_size < 1:
        raise PricingError("تعداد نفرات باید حداقل ۱ نفر باشد.")

    items: list[LineItem] = []

    if space is SpaceCode.VIP:
        if party_size > cfg.vip_max_party:
            raise PricingError(
                f"برای رزرو VIP حداکثر {cfg.vip_max_party} نفر امکان‌پذیر است. "
                "برای گروه‌های بزرگ‌تر به پشتیبانی متصل شوید."
            )
        flat = cfg.vip_flat_up_to_4 if party_size <= 4 else cfg.vip_flat_5_to_10
        items.append(LineItem("space", "رزرو VIP (مبلغ ثابت)", 1, flat, flat))
        space_amount = flat
    else:
        unit = cfg.per_person[space.value]
        space_amount = unit * party_size
        items.append(
            LineItem("space", SPACE_LABELS[space], party_size, unit, space_amount)
        )

    design_amount = 0
    if design is not DesignCode.NONE:
        design_amount = cfg.designs[design.value]
        items.append(
            LineItem("design", DESIGN_LABELS[design], 1, design_amount, design_amount)
        )

    catering_amount = 0
    if with_cake:
        catering_amount = cfg.catering_per_person * party_size
        items.append(
            LineItem(
                "catering",
                "هزینه‌های پذیرایی (کیک)",
                party_size,
                cfg.catering_per_person,
                catering_amount,
            )
        )

    total = space_amount + design_amount + catering_amount
    return Quote(
        items=tuple(items),
        space_amount=space_amount,
        design_amount=design_amount,
        catering_amount=catering_amount,
        total=total,
    )
