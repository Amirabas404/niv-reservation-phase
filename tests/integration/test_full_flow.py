from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.domain.errors import (
    CancellationRequiresSupportError,
    InvalidTransitionError,
    PaymentStateError,
    PermissionDeniedError,
)
from app.domain.permissions import Permission, Role
from app.domain.statuses import ReservationStatus
from app.models import Payment, Reservation, Table
from app.services import admin_service as admin
from app.services import reservation_service as svc
from app.services import support_service as support
from app.services.admin_service import AdminContext
from app.services.jobs_service import claim_job
from app.services.reporting_service import daily_report
from app.worker.jobs import payment_reminders_and_expiry

UTC = ZoneInfo("UTC")
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
START = datetime(2026, 11, 10, 10, 30, tzinfo=UTC)  # 14:00 Tehran
# Design bookings need 5h lead time and paid cancellations need 8h notice: use a booking 10h away.
LATER = NOW + timedelta(hours=10)
MANAGER = AdminContext(telegram_user_id=100, role=Role.MANAGER, display_name="مدیر")
SUPPORT = AdminContext(telegram_user_id=200, role=Role.SUPPORT, display_name="پشتیبان")


async def _table(session, number: str) -> Table:
    t = (await session.execute(select(Table).where(Table.number == number))).scalar_one()
    t.capacity = 6
    await session.commit()
    return t


async def test_plain_reservation_flow_confirms_with_table(session):
    r = await svc.create_reservation(session, now=NOW, customer_name="علی", phone="09120000010",
                                     space_code="hall", party_size=4, booking_start=START,
                                     telegram_user_id=5001)
    assert r.status == ReservationStatus.PENDING_MANAGER.value
    table = await _table(session, "3")
    await svc.confirm_reservation(session, public_code=r.public_code, table_ids=[table.id], actor_telegram_id=100)
    await session.commit()
    assert (await session.get(Reservation, r.id)).status == ReservationStatus.CONFIRMED.value


async def test_design_flow_receipt_verify_confirm(session):
    r = await svc.create_reservation(session, now=NOW, customer_name="سارا", phone="09120000011",
                                     space_code="roof_family", party_size=2, booking_start=LATER,
                                     design="both", telegram_user_id=5002)
    assert r.status == ReservationStatus.AWAITING_PAYMENT.value
    await session.commit()
    await svc.submit_receipt(session, public_code=r.public_code, storage_key="receipts/test.jpg", now=NOW,
                             telegram_user_id=5002)
    payment = (await session.execute(select(Payment).where(Payment.reservation_id == r.id))).scalar_one()
    with pytest.raises(PaymentStateError):
        await svc.verify_payment(session, public_code=r.public_code, amount_verified=1, now=NOW,
                                 actor_telegram_id=100)
    await svc.verify_payment(session, public_code=r.public_code, amount_verified=payment.amount_expected,
                             now=NOW, actor_telegram_id=100)
    table = await _table(session, "14")
    await svc.confirm_reservation(session, public_code=r.public_code, table_ids=[table.id], actor_telegram_id=100)
    await session.commit()
    assert (await session.get(Reservation, r.id)).status == ReservationStatus.CONFIRMED.value


async def test_cancel_paid_design_refunds_half(session):
    r = await svc.create_reservation(session, now=NOW, customer_name="نیلا", phone="09120000012",
                                     space_code="roof_family", party_size=2, booking_start=LATER,
                                     design="balloon_stand", telegram_user_id=5003)
    await session.commit()
    await svc.submit_receipt(session, public_code=r.public_code, storage_key="receipts/x.jpg", now=NOW)
    payment = (await session.execute(select(Payment).where(Payment.reservation_id == r.id))).scalar_one()
    await svc.verify_payment(session, public_code=r.public_code, amount_verified=payment.amount_expected,
                             now=NOW, actor_telegram_id=100)
    table = await _table(session, "15")
    await svc.confirm_reservation(session, public_code=r.public_code, table_ids=[table.id], actor_telegram_id=100)
    await session.commit()
    refund = await svc.cancel_by_customer(session, public_code=r.public_code, now=NOW)
    await session.commit()
    assert refund == payment.amount_expected // 2


async def test_cancellation_inside_cutoff_needs_support(session):
    r = await svc.create_reservation(session, now=NOW, customer_name="زهرا", phone="09120000013",
                                     space_code="hall", party_size=2, booking_start=NOW + timedelta(hours=3))
    await session.commit()
    with pytest.raises(CancellationRequiresSupportError):
        await svc.cancel_by_customer(session, public_code=r.public_code, now=NOW)


async def test_unpaid_design_rejected_after_deadline(session):
    r = await svc.create_reservation(session, now=NOW, customer_name="رضا", phone="09120000014",
                                     space_code="hall", party_size=2, booking_start=LATER,
                                     design="balloon_stand", telegram_user_id=5004)
    await session.commit()
    result = await payment_reminders_and_expiry(session, LATER - timedelta(hours=6))
    await session.commit()
    assert result["rejected"] == 1
    assert (await session.get(Reservation, r.id)).status == ReservationStatus.REJECTED_UNPAID.value


async def test_support_claim_is_exclusive_and_close_notifies_customer(session):
    t, created = await support.open_ticket(session, telegram_user_id=6001, reason="سؤال منو")
    await session.commit()
    assert created is True
    await support.claim(session, SUPPORT, t.id)
    other = AdminContext(telegram_user_id=201, role=Role.SUPPORT, display_name="پشتیبان ۲")
    with pytest.raises(InvalidTransitionError):
        await support.claim(session, other, t.id)
    await support.reply(session, SUPPORT, t.id, "سلام، چطور کمک کنم؟")
    await support.close(session, SUPPORT, t.id)
    await session.commit()
    assert any(m["sender"] == "system" for m in await support.outbox(session))


async def test_support_cannot_confirm_or_see_amounts(session):
    with pytest.raises(PermissionDeniedError):
        admin.require(SUPPORT, Permission.CONFIRM_RESERVATION)
    await svc.create_reservation(session, now=NOW, customer_name="مهدی", phone="09120000015",
                                 space_code="hall", party_size=2, booking_start=START)
    await session.commit()
    rows = await admin.list_reservations(session, SUPPORT, [])
    assert rows and all("total_amount" not in row for row in rows)


async def test_daily_report_counts_booking_day(session):
    await svc.create_reservation(session, now=NOW, customer_name="نرگس", phone="09120000016",
                                 space_code="hall", party_size=3, booking_start=START)
    await session.commit()
    report = await daily_report(session, datetime(2026, 11, 10, tzinfo=UTC).date())
    assert report["spaces"]["hall"]["guests"] == 3


async def test_job_claim_runs_once(session):
    assert await claim_job(session, "nightly:2026-11-10", "nightly_report") is True
    await session.commit()
    assert await claim_job(session, "nightly:2026-11-10", "nightly_report") is False
