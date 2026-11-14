"""Scheduled jobs. Each job claims a run_key in the same transaction as its work, so it runs once
and a failed run is retried on the next tick."""

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.fa import money
from app.domain.calendar_rules import is_last_day_of_month
from app.domain.payment_rules import payment_deadline_passed, payment_reminder_due
from app.domain.statuses import ReservationStatus
from app.excel_export import export_monthly
from app.integrations.telegram_sender import TelegramSender
from app.models import AdminUser, DailyReport, Payment, Reservation
from app.services import notification_service as notes
from app.services.jobs_service import claim_job
from app.services.reporting_service import daily_report
from app.services.report_text import format_daily
from app.services.reservation_service import auto_reject_unpaid
from app.services.settings_service import load_reports, load_rules
from app.worker.backup import run_backup
from app.worker.backup import run_backup

log = logging.getLogger(__name__)

REMINDER_TEXT = (
    "یادآوری پرداخت 🌷\n\n"
    "رزرو {code} هنوز در انتظار پرداخت است.\n"
    "مبلغ قابل پرداخت: {amount}\n\n"
    "لطفاً پیش از مهلت تعیین‌شده، پرداخت را انجام داده و تصویر رسید را همین‌جا ارسال کنید."
)
UNPAID_REJECT_TEXT = (
    "مشتری گرامی 🌷\n\nبه دلیل عدم پرداخت در زمان تعیین‌شده، درخواست رزرو شما رد شد.\n\n"
    "از همراهی شما سپاسگزاریم.\n\nکافه‌رستوران NIV ❤️"
)


def _local_now(now_utc: datetime) -> datetime:
    return now_utc.astimezone(ZoneInfo(get_settings().timezone))


async def payment_reminders_and_expiry(session: AsyncSession, now: datetime) -> dict:
    rules = await load_rules(session)
    rows = (await session.execute(
        select(Reservation, Payment)
        .join(Payment, Payment.reservation_id == Reservation.id)
        .where(Reservation.status == ReservationStatus.AWAITING_PAYMENT.value,
               Payment.payment_reminder_sent_at.is_(None))
        .with_for_update(of=Payment)
    )).all()
    reminded = 0
    for r, p in rows:
        if payment_deadline_passed(now, r.booking_start, rules.payment_deadline_hours_before):
            continue
        if payment_reminder_due(now, r.booking_start, rules.payment_reminder_hours_before) and r.created_by_telegram_id:
            await notes.enqueue(
                session,
                telegram_user_id=r.created_by_telegram_id,
                kind="payment_reminder",
                text=REMINDER_TEXT.format(code=r.public_code, amount=money(p.amount_expected)),
            )
            p.payment_reminder_sent_at = now
            reminded += 1

    rejected = await auto_reject_unpaid(session, now=now)
    for code in rejected:
        owner = (await session.execute(
            select(Reservation.created_by_telegram_id).where(Reservation.public_code == code))).scalar_one_or_none()
        if owner:
            await notes.enqueue(session, telegram_user_id=owner, kind="unpaid_rejected", text=UNPAID_REJECT_TEXT)
    return {"reminded": reminded, "rejected": len(rejected)}


async def _managers(session: AsyncSession) -> list[int]:
    rows = (await session.execute(
        select(AdminUser.telegram_user_id).where(AdminUser.role == "manager", AdminUser.is_active.is_(True))
    )).scalars().all()
    return list(rows)


async def nightly_report(session: AsyncSession, sender: TelegramSender, local_day: date) -> None:
    report = await daily_report(session, local_day)
    session.add(DailyReport(report_date=local_day, payload=report))
    await session.flush()
    text = format_daily(report)
    for chat_id in await _managers(session):
        await sender.send_message(chat_id, text)


async def monthly_export(session: AsyncSession, sender: TelegramSender, year: int, month: int) -> None:
    data, filename, summary = await export_monthly(session, year, month)
    caption = f"گزارش ماهانه رزروها و مالی · {year}-{month:02d}\nخالص درآمد: {summary['net_total']:,} تومان"
    for chat_id in await _managers(session):
        await sender.send_document(chat_id, data, filename, caption)


async def run_scheduled(session_maker: async_sessionmaker, sender: TelegramSender, now_utc: datetime) -> None:
    local = _local_now(now_utc)
    today = local.date()

    async with session_maker() as s:
        result = await payment_reminders_and_expiry(s, now_utc)
        await s.commit()
        if result["reminded"] or result["rejected"]:
            log.info("payments: %s", result)

    reports = None
    async with session_maker() as s:
        reports = await load_reports(s)

    if local.time() >= reports["nightly_time"]:
        async with session_maker() as s:
            if await claim_job(s, f"nightly:{today.isoformat()}", "nightly_report"):
                await nightly_report(s, sender, today)
                await s.commit()
                log.info("nightly report sent for %s", today)

    backup_at = time.fromisoformat(get_settings().backup_time)
    if local.time() >= backup_at:
        async with session_maker() as s:
            if await claim_job(s, f"backup:{today.isoformat()}", "database_backup"):
                await run_backup(get_settings(), local_day=today)
                await s.commit()
                log.info("database backup stored for %s", today)

    backup_at = time.fromisoformat(get_settings().backup_time)
    if local.time() >= backup_at:
        async with session_maker() as s:
            if await claim_job(s, f"backup:{today.isoformat()}", "database_backup"):
                await run_backup(get_settings(), local_day=today)
                await s.commit()
                log.info("database backup stored for %s", today)

    if is_last_day_of_month(today) and local.time() >= reports["monthly_time"]:
        async with session_maker() as s:
            key = f"monthly:{today.year}-{today.month:02d}"
            if await claim_job(s, key, "monthly_export"):
                await monthly_export(s, sender, today.year, today.month)
                await s.commit()
                log.info("monthly export sent for %s", key)
