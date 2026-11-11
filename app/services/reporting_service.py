"""Daily and monthly reporting. Financial figures use VERIFIED payments only."""

from collections import defaultdict
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import to_jalali_str
from app.domain.calendar_rules import day_bounds_utc, month_bounds_utc
from app.models import Customer, Payment, Reservation, Space, Table, TableBooking
from app.core.config import get_settings

REMOVED = {"cancelled", "rejected", "rejected_unpaid"}
PENDING = {"pending_manager_approval", "awaiting_payment", "receipt_submitted"}


def _tz(_session: AsyncSession | None = None) -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


async def daily_report(session: AsyncSession, day: date) -> dict:
    tz = _tz(session)
    start, end = day_bounds_utc(day, tz)

    requested_today = (await session.execute(
        select(func.count(Reservation.id)).where(Reservation.requested_at >= start, Reservation.requested_at < end)
    )).scalar_one()

    rows = (await session.execute(
        select(Reservation, Space.code, Space.name, Payment.status, Payment.amount_verified)
        .join(Space, Space.id == Reservation.space_id)
        .outerjoin(Payment, Payment.reservation_id == Reservation.id)
        .where(Reservation.booking_start >= start, Reservation.booking_start < end,
               Reservation.deleted_at.is_(None))
    )).all()

    by_status: dict[str, int] = defaultdict(int)
    spaces: dict[str, dict] = {}
    pay_counts: dict[str, int] = defaultdict(int)
    verified_total = 0
    party_total = 0
    for r, space_code, space_name, pay_status, verified in rows:
        by_status[r.status] += 1
        if pay_status:
            pay_counts[pay_status] += 1
        if pay_status == "verified" and verified:
            verified_total += verified
        if r.status not in REMOVED:
            entry = spaces.setdefault(space_code, {"name": space_name, "reservations": 0, "guests": 0})
            entry["reservations"] += 1
            entry["guests"] += r.party_size
            party_total += r.party_size

    tables_total = (await session.execute(select(func.count(Table.id)))).scalar_one()
    tables_blocked = (await session.execute(select(func.count(Table.id)).where(Table.is_blocked.is_(True)))).scalar_one()
    tables_unset = (await session.execute(select(func.count(Table.id)).where(Table.capacity.is_(None)))).scalar_one()

    return {
        "date_jalali": to_jalali_str(start, with_time=False),
        "requested_today": requested_today,
        "confirmed": by_status.get("confirmed", 0),
        "rejected": by_status.get("rejected", 0) + by_status.get("rejected_unpaid", 0),
        "cancelled": by_status.get("cancelled", 0),
        "pending": sum(by_status.get(s, 0) for s in PENDING),
        "payments": dict(pay_counts),
        "verified_amount": verified_total,
        "guests_total": party_total,
        "spaces": spaces,
        "tables": {"total": tables_total, "blocked": tables_blocked, "capacity_not_set": tables_unset},
    }


async def monthly_rows(session: AsyncSession, year: int, month: int) -> list[dict]:
    tz = _tz(session)
    start, end = month_bounds_utc(year, month, tz)
    rows = (await session.execute(
        select(Reservation, Customer.full_name, Customer.phone, Space.name, Payment.status,
               Payment.amount_verified, Payment.refund_amount)
        .join(Customer, Customer.id == Reservation.customer_id)
        .join(Space, Space.id == Reservation.space_id)
        .outerjoin(Payment, Payment.reservation_id == Reservation.id)
        .where(Reservation.booking_start >= start, Reservation.booking_start < end,
               Reservation.deleted_at.is_(None))
        .order_by(Reservation.booking_start)
    )).all()

    ids = [r.id for r, *_ in rows]
    tables_by_res: dict[int, list[str]] = defaultdict(list)
    if ids:
        for rid, number in (await session.execute(
            select(TableBooking.reservation_id, Table.number)
            .join(Table, Table.id == TableBooking.table_id)
            .where(TableBooking.reservation_id.in_(ids), TableBooking.is_active.is_(True))
            .order_by(Table.id)
        )).all():
            tables_by_res[rid].append(number)

    out = []
    for r, name, phone, space_name, pay_status, verified, refund in rows:
        snap = r.price_snapshot or {}
        out.append({
            "booking_date": to_jalali_str(r.booking_start, with_time=False),
            "booking_time": to_jalali_str(r.booking_start).split(" ")[-1],
            "customer_name": name,
            "customer_phone": phone,
            "party_size": r.party_size,
            "space": space_name,
            "tables": "، ".join(tables_by_res.get(r.id, [])),
            "design": r.design,
            "space_amount": snap.get("space_amount", 0),
            "catering_amount": snap.get("catering_amount", 0),
            "total_amount": r.total_amount,
            "paid_amount": verified or 0,
            "refund_amount": refund or 0,
            "reservation_status": r.status,
            "payment_status": pay_status or "—",
        })
    return out


async def monthly_summary(session: AsyncSession, year: int, month: int) -> dict:
    tz = _tz(session)
    start, end = month_bounds_utc(year, month, tz)
    verified = (await session.execute(
        select(func.coalesce(func.sum(Payment.amount_verified), 0)).where(
            Payment.status == "verified", Payment.verified_at >= start, Payment.verified_at < end)
    )).scalar_one()
    refunds = (await session.execute(
        select(func.coalesce(func.sum(Payment.refund_amount), 0)).where(
            Payment.refund_amount.is_not(None), Payment.updated_at >= start, Payment.updated_at < end)
    )).scalar_one()
    return {
        "verified_payments_total": int(verified),
        "refunds_total": int(refunds),
        "net_total": int(verified) - int(refunds),
    }
