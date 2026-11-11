"""Use cases for reservations. Services flush but never commit; the caller commits."""

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime

from app.core.phone import normalize_phone
from app.core.timezone import ensure_aware, to_local
from app.domain.errors import (
    CancellationRequiresSupportError,
    CapacityNotConfiguredError,
    DomainError,
    NotFoundError,
    PaymentStateError,
    TableConflictError,
)
from app.domain.payment_rules import payment_deadline_passed, refund_amount
from app.domain.pricing import DesignCode, Quote, SpaceCode, compute_quote
from app.domain.statuses import PaymentStatus, ReservationStatus, assert_transition
from app.domain.time_rules import (
    can_cancel_self_service,
    check_design_lead_time,
    validate_dine_in_start,
)
from app.models import AuditLog, Customer, Payment, Reservation, Space, Table, TableBooking
from app.services.settings_service import load_pricing, load_rules

UTC = ZoneInfo("UTC")
_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_CANCELLABLE = {
    ReservationStatus.PENDING_MANAGER.value,
    ReservationStatus.AWAITING_PAYMENT.value,
    ReservationStatus.RECEIPT_SUBMITTED.value,
    ReservationStatus.CONFIRMED.value,
}


def _new_public_code() -> str:
    return "NIV-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


async def _audit(session: AsyncSession, actor: int | None, action: str, entity: str, entity_id: str, payload: dict) -> None:
    session.add(
        AuditLog(
            actor_telegram_id=actor,
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            payload=payload,
        )
    )


async def _get_space(session: AsyncSession, code: SpaceCode) -> Space:
    space = (await session.execute(select(Space).where(Space.code == code.value))).scalar_one_or_none()
    if space is None or not space.is_active:
        raise NotFoundError("فضای انتخابی یافت نشد.")
    return space


async def _get_reservation_for_update(session: AsyncSession, public_code: str) -> Reservation:
    reservation = (
        await session.execute(
            select(Reservation)
            .where(Reservation.public_code == public_code, Reservation.deleted_at.is_(None))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if reservation is None:
        raise NotFoundError("رزرو با این کد یافت نشد.")
    return reservation


async def _get_payment(session: AsyncSession, reservation_id: int, for_update: bool = False) -> Payment | None:
    stmt = select(Payment).where(Payment.reservation_id == reservation_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _validate_request(
    session: AsyncSession,
    *,
    now: datetime,
    space_code: SpaceCode,
    party_size: int,
    booking_start: datetime,
    design: DesignCode,
    with_cake: bool,
) -> tuple[Quote, datetime]:
    ensure_aware(now)
    ensure_aware(booking_start)
    rules = await load_rules(session)
    pricing = await load_pricing(session)

    start_utc = booking_start.astimezone(UTC)
    now_utc = now.astimezone(UTC)

    validate_dine_in_start(to_local(start_utc), to_local(now_utc), rules)
    if design is not DesignCode.NONE:
        check_design_lead_time(now_utc, start_utc, rules)

    quote = compute_quote(pricing, space_code, party_size, design, with_cake)
    return quote, start_utc


async def quote_reservation(
    session: AsyncSession,
    *,
    now: datetime,
    space_code: SpaceCode | str,
    party_size: int,
    booking_start: datetime,
    design: DesignCode | str = DesignCode.NONE,
    with_cake: bool = False,
) -> Quote:
    quote, _ = await _validate_request(
        session,
        now=now,
        space_code=SpaceCode(space_code),
        party_size=party_size,
        booking_start=booking_start,
        design=DesignCode(design),
        with_cake=with_cake,
    )
    return quote


async def create_reservation(
    session: AsyncSession,
    *,
    now: datetime,
    customer_name: str,
    phone: str,
    space_code: SpaceCode | str,
    party_size: int,
    booking_start: datetime,
    design: DesignCode | str = DesignCode.NONE,
    with_cake: bool = False,
    notes: str | None = None,
    telegram_user_id: int | None = None,
) -> Reservation:
    phone_norm = normalize_phone(phone)
    space_enum = SpaceCode(space_code)
    design_enum = DesignCode(design)

    quote, start_utc = await _validate_request(
        session,
        now=now,
        space_code=space_enum,
        party_size=party_size,
        booking_start=booking_start,
        design=design_enum,
        with_cake=with_cake,
    )
    rules = await load_rules(session)
    space = await _get_space(session, space_enum)

    customer = (await session.execute(select(Customer).where(Customer.phone == phone_norm))).scalar_one_or_none()
    if customer is None:
        customer = Customer(phone=phone_norm, full_name=customer_name.strip())
        session.add(customer)
    else:
        customer.full_name = customer_name.strip()
    await session.flush()

    has_design = design_enum is not DesignCode.NONE
    status = ReservationStatus.AWAITING_PAYMENT if has_design else ReservationStatus.PENDING_MANAGER

    reservation = Reservation(
        public_code=_new_public_code(),
        branch_id=space.branch_id,
        customer_id=customer.id,
        space_id=space.id,
        party_size=party_size,
        requested_at=now.astimezone(UTC),
        booking_start=start_utc,
        booking_end=start_utc + timedelta(minutes=rules.reservation_duration_minutes),
        service_type="dine_in",
        design=design_enum.value,
        with_cake=with_cake,
        status=status.value,
        total_amount=quote.total,
        price_snapshot=quote.to_snapshot(),
        customer_notes=notes,
        created_by_telegram_id=telegram_user_id,
    )
    session.add(reservation)
    await session.flush()

    if has_design:
        session.add(
            Payment(
                reservation_id=reservation.id,
                amount_expected=quote.total,
                status=PaymentStatus.PENDING.value,
            )
        )

    await _audit(
        session,
        telegram_user_id,
        "reservation.created",
        "reservation",
        str(reservation.id),
        {"status": status.value, "total": quote.total},
    )
    await session.flush()
    return reservation


async def submit_receipt(
    session: AsyncSession,
    *,
    public_code: str,
    storage_key: str,
    now: datetime,
    telegram_user_id: int | None = None,
) -> None:
    reservation = await _get_reservation_for_update(session, public_code)
    payment = await _get_payment(session, reservation.id, for_update=True)
    if payment is None:
        raise PaymentStateError("این رزرو پرداخت کارت‌به‌کارت ندارد.")
    if payment.status not in (PaymentStatus.PENDING.value, PaymentStatus.REJECTED.value):
        raise PaymentStateError("رسید این رزرو قبلاً ثبت شده است.")

    assert_transition(reservation.status, ReservationStatus.RECEIPT_SUBMITTED)
    reservation.status = ReservationStatus.RECEIPT_SUBMITTED.value
    payment.status = PaymentStatus.RECEIPT_SUBMITTED.value
    payment.receipt_storage_key = storage_key
    payment.receipt_submitted_at = now.astimezone(UTC)
    await _audit(session, telegram_user_id, "payment.receipt_submitted", "reservation", public_code, {})


async def verify_payment(
    session: AsyncSession,
    *,
    public_code: str,
    amount_verified: int,
    now: datetime,
    actor_telegram_id: int,
) -> None:
    reservation = await _get_reservation_for_update(session, public_code)
    payment = await _get_payment(session, reservation.id, for_update=True)
    if payment is None or payment.status != PaymentStatus.RECEIPT_SUBMITTED.value:
        raise PaymentStateError("این پرداخت در وضعیت بررسی نیست.")
    if amount_verified != payment.amount_expected:
        raise PaymentStateError(
            f"مبلغ تأییدشده ({amount_verified:,}) با مبلغ رزرو ({payment.amount_expected:,}) برابر نیست."
        )
    payment.status = PaymentStatus.VERIFIED.value
    payment.amount_verified = amount_verified
    payment.verified_at = now.astimezone(UTC)
    payment.verified_by_telegram_id = actor_telegram_id
    await _audit(session, actor_telegram_id, "payment.verified", "reservation", public_code, {"amount": amount_verified})


async def reject_payment(
    session: AsyncSession,
    *,
    public_code: str,
    reason: str,
    actor_telegram_id: int,
) -> None:
    reservation = await _get_reservation_for_update(session, public_code)
    payment = await _get_payment(session, reservation.id, for_update=True)
    if payment is None or payment.status != PaymentStatus.RECEIPT_SUBMITTED.value:
        raise PaymentStateError("این پرداخت در وضعیت بررسی نیست.")
    assert_transition(reservation.status, ReservationStatus.AWAITING_PAYMENT)
    reservation.status = ReservationStatus.AWAITING_PAYMENT.value
    payment.status = PaymentStatus.REJECTED.value
    payment.rejection_reason = reason
    await _audit(session, actor_telegram_id, "payment.rejected", "reservation", public_code, {"reason": reason})


async def confirm_reservation(
    session: AsyncSession,
    *,
    public_code: str,
    table_ids: list[int],
    actor_telegram_id: int,
) -> Reservation:
    """Manager confirms a reservation and assigns tables atomically.

    Plain reservation: must be pending manager approval.
    Design reservation: payment must be verified first.
    """
    reservation = await _get_reservation_for_update(session, public_code)
    if reservation.design != DesignCode.NONE.value:
        payment = await _get_payment(session, reservation.id)
        if payment is None or payment.status != PaymentStatus.VERIFIED.value:
            raise PaymentStateError("پرداخت این رزرو هنوز تأیید نشده است.")
    elif reservation.status != ReservationStatus.PENDING_MANAGER.value:
        raise DomainError("این رزرو در وضعیت تأیید مدیر نیست.")
    assert_transition(reservation.status, ReservationStatus.CONFIRMED)

    unique_ids = sorted(set(table_ids))
    tables = (
        await session.execute(select(Table).where(Table.id.in_(unique_ids)).order_by(Table.id).with_for_update())
    ).scalars().all()
    if len(tables) != len(unique_ids):
        raise NotFoundError("یک یا چند میز انتخابی یافت نشد.")
    for t in tables:
        if t.space_id != reservation.space_id:
            raise DomainError("میز انتخابی متعلق به فضای این رزرو نیست.")
        if t.is_blocked or not t.is_active:
            raise DomainError(f"میز {t.number} در حال حاضر مسدود یا غیرفعال است.")
        if t.capacity is None:
            raise CapacityNotConfiguredError(f"ظرفیت میز {t.number} هنوز تنظیم نشده است.")
    if sum(t.capacity for t in tables) < reservation.party_size:
        raise DomainError("مجموع ظرفیت میزهای انتخابی کمتر از تعداد نفرات است.")

    try:
        async with session.begin_nested():
            for t in tables:
                await session.execute(
                    insert(TableBooking).values(
                        table_id=t.id,
                        reservation_id=reservation.id,
                        booking_range=func.tstzrange(
                            literal(reservation.booking_start, DateTime(timezone=True)),
                            literal(reservation.booking_end, DateTime(timezone=True)),
                            literal("[)"),
                        ),
                        kind="reservation",
                        is_active=True,
                    )
                )
    except IntegrityError as exc:
        raise TableConflictError("یکی از میزهای انتخابی در این بازه زمانی رزرو شده است.") from exc

    reservation.status = ReservationStatus.CONFIRMED.value
    await _audit(
        session,
        actor_telegram_id,
        "reservation.confirmed",
        "reservation",
        public_code,
        {"table_ids": unique_ids},
    )
    await session.flush()
    return reservation


async def reject_reservation(
    session: AsyncSession,
    *,
    public_code: str,
    reason: str,
    actor_telegram_id: int,
) -> None:
    reservation = await _get_reservation_for_update(session, public_code)
    assert_transition(reservation.status, ReservationStatus.REJECTED)
    reservation.status = ReservationStatus.REJECTED.value
    await _audit(session, actor_telegram_id, "reservation.rejected", "reservation", public_code, {"reason": reason})


async def cancel_by_customer(
    session: AsyncSession,
    *,
    public_code: str,
    now: datetime,
    telegram_user_id: int | None = None,
) -> int:
    """Self-service cancellation up to the cutoff. Returns the refund amount (Toman).

    Refund = refund_percent of the VERIFIED amount only. Unverified payments are not refunded.
    Actual bank transfer is manual and recorded by staff.
    """
    rules = await load_rules(session)
    reservation = await _get_reservation_for_update(session, public_code)
    if reservation.status not in _CANCELLABLE:
        raise DomainError("این رزرو قابل لغو نیست.")
    if not can_cancel_self_service(ensure_aware(now).astimezone(UTC), reservation.booking_start, rules):
        raise CancellationRequiresSupportError(
            f"لغو کمتر از {rules.cancellation_cutoff_hours} ساعت قبل از رزرو از طریق پشتیبانی انجام می‌شود."
        )

    refund = 0
    payment = await _get_payment(session, reservation.id, for_update=True)
    if payment is not None and payment.status == PaymentStatus.VERIFIED.value:
        refund = refund_amount(payment.amount_verified or 0, rules.refund_percent)
        payment.refund_amount = refund

    assert_transition(reservation.status, ReservationStatus.CANCELLED)
    reservation.status = ReservationStatus.CANCELLED.value
    await session.execute(
        update(TableBooking)
        .where(TableBooking.reservation_id == reservation.id)
        .values(is_active=False)
    )
    await _audit(
        session,
        telegram_user_id,
        "reservation.cancelled",
        "reservation",
        public_code,
        {"refund": refund},
    )
    await session.flush()
    return refund


async def auto_reject_unpaid(session: AsyncSession, *, now: datetime) -> list[str]:
    """Reject design reservations whose payment deadline has passed. Records are kept."""
    rules = await load_rules(session)
    now_utc = ensure_aware(now).astimezone(UTC)
    rows = (
        await session.execute(
            select(Reservation)
            .where(Reservation.status == ReservationStatus.AWAITING_PAYMENT.value)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    rejected: list[str] = []
    for r in rows:
        if not payment_deadline_passed(now_utc, r.booking_start, rules.payment_deadline_hours_before):
            continue
        assert_transition(r.status, ReservationStatus.REJECTED_UNPAID)
        r.status = ReservationStatus.REJECTED_UNPAID.value
        payment = await _get_payment(session, r.id, for_update=True)
        if payment is not None and payment.status == PaymentStatus.PENDING.value:
            payment.status = PaymentStatus.REJECTED.value
            payment.rejection_reason = "عدم پرداخت در زمان تعیین‌شده"
        await _audit(session, None, "reservation.auto_rejected_unpaid", "reservation", r.public_code, {})
        rejected.append(r.public_code)
    await session.flush()
    return rejected
