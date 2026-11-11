from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConfigurationError
from app.domain.pricing import PricingConfig
from app.domain.time_rules import RulesConfig
from app.models import SystemSetting


async def _get_setting(session: AsyncSession, key: str) -> dict:
    row = await session.get(SystemSetting, key)
    if row is None:
        raise ConfigurationError(f"تنظیم «{key}» در پایگاه داده موجود نیست.")
    return row.value


async def load_pricing(session: AsyncSession) -> PricingConfig:
    v = await _get_setting(session, "pricing")
    return PricingConfig(
        per_person=v["per_person"],
        vip_flat_up_to_4=v["vip_flat_up_to_4"],
        vip_flat_5_to_10=v["vip_flat_5_to_10"],
        vip_max_party=v["vip_max_party"],
        designs=v["designs"],
        catering_per_person=v["catering_per_person"],
    )


async def load_rules(session: AsyncSession) -> RulesConfig:
    v = await _get_setting(session, "rules")
    return RulesConfig(
        dine_in_open=time.fromisoformat(v["dine_in_open"]),
        dine_in_close=time.fromisoformat(v["dine_in_close"]),
        design_min_lead_hours=v["design_min_lead_hours"],
        cancellation_cutoff_hours=v["cancellation_cutoff_hours"],
        reservation_duration_minutes=v["reservation_duration_minutes"],
        payment_reminder_hours_before=v["payment_reminder_hours_before"],
        payment_deadline_hours_before=v["payment_deadline_hours_before"],
        refund_percent=v["refund_percent"],
    )


async def load_bank_card(session: AsyncSession) -> dict:
    """Card details are set by the manager/admin in the database, never in code."""
    return await _get_setting(session, "bank_card")


async def load_reports(session: AsyncSession) -> dict:
    v = await _get_setting(session, "reports")
    return {"nightly_time": time.fromisoformat(v["nightly_time"]), "monthly_time": time.fromisoformat(v["monthly_time"])}
