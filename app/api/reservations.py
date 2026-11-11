from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_service_token
from app.core.timezone import utc_now
from app.schemas.reservations import (
    CancelOut,
    CancelRequest,
    ConfirmRequest,
    CreateReservationRequest,
    QuoteOut,
    QuoteRequest,
    ReceiptRequest,
    RejectRequest,
    ReservationOut,
    VerifyPaymentRequest,
)
from app.services import reservation_service as svc

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(require_service_token)],
)


@router.post("/quote", response_model=QuoteOut)
async def quote(body: QuoteRequest, session: AsyncSession = Depends(get_session)) -> QuoteOut:
    q = await svc.quote_reservation(
        session,
        now=utc_now(),
        space_code=body.space_code,
        party_size=body.party_size,
        booking_start=body.booking_start,
        design=body.design,
        with_cake=body.with_cake,
    )
    return QuoteOut(
        total=q.total,
        space_amount=q.space_amount,
        design_amount=q.design_amount,
        catering_amount=q.catering_amount,
        items=q.to_snapshot()["items"],
    )


@router.post("/reservations", response_model=ReservationOut, status_code=201)
async def create_reservation(
    body: CreateReservationRequest, session: AsyncSession = Depends(get_session)
) -> ReservationOut:
    r = await svc.create_reservation(session, now=utc_now(), **body.model_dump())
    await session.commit()
    return ReservationOut(
        public_code=r.public_code,
        status=r.status,
        total_amount=r.total_amount,
        price_snapshot=r.price_snapshot,
    )


@router.post("/reservations/{public_code}/receipt", status_code=204)
async def submit_receipt(
    public_code: str, body: ReceiptRequest, session: AsyncSession = Depends(get_session)
) -> None:
    await svc.submit_receipt(
        session,
        public_code=public_code,
        storage_key=body.storage_key,
        now=utc_now(),
        telegram_user_id=body.telegram_user_id,
    )
    await session.commit()


@router.post("/reservations/{public_code}/payment/verify", status_code=204)
async def verify_payment(
    public_code: str, body: VerifyPaymentRequest, session: AsyncSession = Depends(get_session)
) -> None:
    await svc.verify_payment(
        session,
        public_code=public_code,
        amount_verified=body.amount_verified,
        now=utc_now(),
        actor_telegram_id=body.actor_telegram_id,
    )
    await session.commit()


@router.post("/reservations/{public_code}/payment/reject", status_code=204)
async def reject_payment(
    public_code: str, body: RejectRequest, session: AsyncSession = Depends(get_session)
) -> None:
    await svc.reject_payment(
        session, public_code=public_code, reason=body.reason, actor_telegram_id=body.actor_telegram_id
    )
    await session.commit()


@router.post("/reservations/{public_code}/confirm", response_model=ReservationOut)
async def confirm(
    public_code: str, body: ConfirmRequest, session: AsyncSession = Depends(get_session)
) -> ReservationOut:
    r = await svc.confirm_reservation(
        session,
        public_code=public_code,
        table_ids=body.table_ids,
        actor_telegram_id=body.actor_telegram_id,
    )
    await session.commit()
    return ReservationOut(
        public_code=r.public_code,
        status=r.status,
        total_amount=r.total_amount,
        price_snapshot=r.price_snapshot,
    )


@router.post("/reservations/{public_code}/reject", status_code=204)
async def reject(
    public_code: str, body: RejectRequest, session: AsyncSession = Depends(get_session)
) -> None:
    await svc.reject_reservation(
        session, public_code=public_code, reason=body.reason, actor_telegram_id=body.actor_telegram_id
    )
    await session.commit()


@router.post("/reservations/{public_code}/cancel", response_model=CancelOut)
async def cancel(
    public_code: str, body: CancelRequest, session: AsyncSession = Depends(get_session)
) -> CancelOut:
    refund = await svc.cancel_by_customer(
        session, public_code=public_code, now=utc_now(), telegram_user_id=body.telegram_user_id
    )
    await session.commit()
    return CancelOut(refund_amount=refund)
