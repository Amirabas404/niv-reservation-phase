import secrets

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.timezone import utc_now
from app.domain.errors import PermissionDeniedError
from app.domain.permissions import permissions_of
from app.integrations.storage import get_storage
from app.schemas.admin import (
    AdminMe,
    ConfirmByAdmin,
    PaymentVerifyByAdmin,
    RejectByAdmin,
    SettingUpdate,
    TableUpdate,
)
from app.services import admin_service as admin
from app.services import reservation_service as svc

router = APIRouter(prefix="/admin", tags=["admin"])


async def admin_context(
    x_admin_token: str = Header(default=""),
    x_actor_telegram_id: int = Header(default=0),
    session: AsyncSession = Depends(get_session),
) -> admin.AdminContext:
    expected = get_settings().admin_service_token.get_secret_value()
    if not secrets.compare_digest(x_admin_token, expected):
        raise PermissionDeniedError("درخواست مجاز نیست.")
    if x_actor_telegram_id <= 0:
        raise PermissionDeniedError("شناسه کاربر معتبر نیست.")
    return await admin.resolve_admin(session, x_actor_telegram_id)


@router.get("/me", response_model=AdminMe)
async def me(ctx: admin.AdminContext = Depends(admin_context)) -> AdminMe:
    return AdminMe(telegram_user_id=ctx.telegram_user_id, role=ctx.role.value,
                   display_name=ctx.display_name, permissions=permissions_of(ctx.role))


@router.get("/reservations")
async def reservations(
    status: list[str] = Query(default=[]),
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await admin.list_reservations(session, ctx, status)


@router.post("/reservations/{public_code}/confirm")
async def confirm(
    public_code: str,
    body: ConfirmByAdmin,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    admin.require(ctx, admin.Permission.CONFIRM_RESERVATION)
    r = await svc.confirm_reservation(session, public_code=public_code, table_ids=body.table_ids,
                                      actor_telegram_id=ctx.telegram_user_id)
    await session.commit()
    return {"public_code": r.public_code, "status": r.status}


@router.post("/reservations/{public_code}/reject", status_code=204)
async def reject(
    public_code: str,
    body: RejectByAdmin,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin.require(ctx, admin.Permission.REJECT_RESERVATION)
    await svc.reject_reservation(session, public_code=public_code, reason=body.reason,
                                 actor_telegram_id=ctx.telegram_user_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/reservations/{public_code}/payment/verify", status_code=204)
async def verify_payment(
    public_code: str,
    body: PaymentVerifyByAdmin,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin.require(ctx, admin.Permission.VERIFY_PAYMENT)
    await svc.verify_payment(session, public_code=public_code, amount_verified=body.amount_verified,
                             now=utc_now(), actor_telegram_id=ctx.telegram_user_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/reservations/{public_code}/payment/reject", status_code=204)
async def reject_payment(
    public_code: str,
    body: RejectByAdmin,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin.require(ctx, admin.Permission.VERIFY_PAYMENT)
    await svc.reject_payment(session, public_code=public_code, reason=body.reason,
                             actor_telegram_id=ctx.telegram_user_id)
    await session.commit()
    return Response(status_code=204)


@router.get("/reservations/{public_code}/receipt")
async def receipt(
    public_code: str,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    key = await admin.receipt_key(session, ctx, public_code)
    data = await get_storage().read(key)
    await session.commit()
    media = "image/png" if key.endswith(".png") else "image/webp" if key.endswith(".webp") else "image/jpeg"
    return Response(content=data, media_type=media, headers={"Cache-Control": "no-store"})


@router.get("/tables")
async def tables(
    space_code: str | None = None,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await admin.list_tables(session, ctx, space_code)


@router.patch("/tables/{table_id}", status_code=204)
async def patch_table(
    table_id: int,
    body: TableUpdate,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await admin.update_table(session, ctx, table_id, body.capacity, body.is_blocked)
    await session.commit()
    return Response(status_code=204)


@router.get("/settings/{key}")
async def get_setting(
    key: str,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await admin.get_setting(session, ctx, key)


@router.put("/settings/{key}")
async def put_setting(
    key: str,
    body: SettingUpdate,
    ctx: admin.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await admin.update_setting(session, ctx, key, body.value, body.expected_version)
    await session.commit()
    return result
