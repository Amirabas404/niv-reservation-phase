"""Read and upload endpoints used by the customer bot."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_service_token
from app.core.config import get_settings
from app.core.phone import normalize_phone
from app.core.timezone import utc_now
from app.domain.errors import ConfigurationError
from app.integrations.storage import ALLOWED_RECEIPT_TYPES, MAX_RECEIPT_BYTES, get_storage
from app.models import Branch, Customer, Payment, Reservation, Space
from app.services import reservation_service as svc
from app.services.settings_service import load_bank_card, load_rules

router = APIRouter(prefix="/internal", tags=["lookup"], dependencies=[Depends(require_service_token)])


@router.get("/venue")
async def venue(session: AsyncSession = Depends(get_session)) -> dict:
    branch = (
        await session.execute(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.id).limit(1))
    ).scalar_one()
    rules = await load_rules(session)
    try:
        card = await load_bank_card(session)
    except ConfigurationError:
        card = {}
    return {
        "name": branch.name,
        "address": branch.address,
        "phone": branch.phone,
        "dine_in_open": rules.dine_in_open.strftime("%H:%M"),
        "dine_in_close": rules.dine_in_close.strftime("%H:%M"),
        "card_number": card.get("card_number"),
        "card_owner": card.get("owner_name"),
    }


@router.get("/customers/{phone}/reservations")
async def customer_reservations(phone: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    phone_norm = normalize_phone(phone)
    rows = (
        await session.execute(
            select(Reservation, Space.name, Payment.status)
            .join(Customer, Customer.id == Reservation.customer_id)
            .join(Space, Space.id == Reservation.space_id)
            .outerjoin(Payment, Payment.reservation_id == Reservation.id)
            .where(Customer.phone == phone_norm, Reservation.deleted_at.is_(None))
            .order_by(Reservation.booking_start.desc())
            .limit(20)
        )
    ).all()
    return [
        {
            "public_code": r.public_code,
            "status": r.status,
            "booking_start": r.booking_start.isoformat(),
            "party_size": r.party_size,
            "space_name": space_name,
            "design": r.design,
            "total_amount": r.total_amount,
            "payment_status": payment_status,
        }
        for r, space_name, payment_status in rows
    ]


@router.post("/reservations/{public_code}/receipts", status_code=status.HTTP_204_NO_CONTENT)
async def upload_receipt(
    public_code: str,
    file: UploadFile = File(...),
    telegram_user_id: int | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    if file.content_type not in ALLOWED_RECEIPT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="فرمت فایل مجاز نیست.")
    data = await file.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="حجم فایل زیاد است.")

    key = await get_storage().save(data, file.content_type)
    await svc.submit_receipt(
        session, public_code=public_code, storage_key=key, now=utc_now(), telegram_user_id=telegram_user_id
    )
    await session.commit()
