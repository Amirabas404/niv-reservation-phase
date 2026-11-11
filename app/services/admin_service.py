"""Management use cases. Every function receives the acting admin and checks permissions first."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import NotFoundError, PermissionDeniedError, SettingsVersionConflictError
from app.domain.permissions import Permission, Role, has_permission, redact_amounts
from app.domain.settings_validation import validate_setting
from app.models import AdminUser, Customer, Payment, Reservation, Space, SystemSetting, Table, AuditLog
from app.domain.errors import DomainError


class AdminContext:
    def __init__(self, telegram_user_id: int, role: Role, display_name: str) -> None:
        self.telegram_user_id = telegram_user_id
        self.role = role
        self.display_name = display_name


def require(ctx: AdminContext, permission: Permission) -> None:
    if not has_permission(ctx.role, permission):
        raise PermissionDeniedError("دسترسی لازم برای این کار را ندارید.")


async def resolve_admin(session: AsyncSession, telegram_user_id: int) -> AdminContext:
    admin = (
        await session.execute(
            select(AdminUser).where(AdminUser.telegram_user_id == telegram_user_id, AdminUser.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if admin is None:
        raise PermissionDeniedError("شما به این ربات دسترسی ندارید.")
    return AdminContext(admin.telegram_user_id, Role(admin.role), admin.display_name)


async def list_reservations(session: AsyncSession, ctx: AdminContext, statuses: list[str]) -> list[dict]:
    require(ctx, Permission.VIEW_RESERVATIONS)
    stmt = (
        select(Reservation, Customer.full_name, Customer.phone, Space.code, Space.name, Payment.status, Payment.amount_expected)
        .join(Customer, Customer.id == Reservation.customer_id)
        .join(Space, Space.id == Reservation.space_id)
        .outerjoin(Payment, Payment.reservation_id == Reservation.id)
        .where(Reservation.deleted_at.is_(None))
        .order_by(Reservation.booking_start)
        .limit(100)
    )
    if statuses:
        stmt = stmt.where(Reservation.status.in_(statuses))
    rows = (await session.execute(stmt)).all()
    out = []
    for r, name, phone, space_code, space_name, pay_status, expected in rows:
        record = {
            "public_code": r.public_code,
            "status": r.status,
            "booking_start": r.booking_start.isoformat(),
            "party_size": r.party_size,
            "space_code": space_code,
            "space_name": space_name,
            "design": r.design,
            "with_cake": r.with_cake,
            "customer_name": name,
            "customer_phone": phone,
            "payment_status": pay_status,
            "total_amount": r.total_amount,
            "amount_expected": expected,
            "has_receipt": pay_status in ("receipt_submitted", "under_review", "verified"),
        }
        out.append(redact_amounts(record, ctx.role))
    return out


async def receipt_key(session: AsyncSession, ctx: AdminContext, public_code: str) -> str:
    require(ctx, Permission.VIEW_RECEIPTS)
    row = (
        await session.execute(
            select(Payment.receipt_storage_key)
            .join(Reservation, Reservation.id == Payment.reservation_id)
            .where(Reservation.public_code == public_code)
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("رسیدی برای این رزرو ثبت نشده است.")
    session.add(AuditLog(actor_telegram_id=ctx.telegram_user_id, action="receipt.viewed",
                         entity_type="reservation", entity_id=public_code, payload={}))
    return row


async def list_tables(session: AsyncSession, ctx: AdminContext, space_code: str | None) -> list[dict]:
    require(ctx, Permission.MANAGE_TABLES)
    stmt = select(Table, Space.code, Space.name).join(Space, Space.id == Table.space_id).order_by(Space.id, Table.id)
    if space_code:
        stmt = stmt.where(Space.code == space_code)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": t.id,
            "number": t.number,
            "capacity": t.capacity,
            "is_blocked": t.is_blocked,
            "is_active": t.is_active,
            "space_code": code,
            "space_name": name,
        }
        for t, code, name in rows
    ]


async def update_table(
    session: AsyncSession, ctx: AdminContext, table_id: int, capacity: int | None, is_blocked: bool | None
) -> None:
    require(ctx, Permission.MANAGE_TABLES)
    table = (await session.execute(select(Table).where(Table.id == table_id).with_for_update())).scalar_one_or_none()
    if table is None:
        raise NotFoundError("میز یافت نشد.")
    if capacity is not None:
        if not 1 <= capacity <= 30:
            raise DomainError("ظرفیت میز باید بین ۱ و ۳۰ باشد.")
        table.capacity = capacity
    if is_blocked is not None:
        table.is_blocked = is_blocked
    session.add(AuditLog(actor_telegram_id=ctx.telegram_user_id, action="table.updated",
                         entity_type="table", entity_id=str(table_id),
                         payload={"capacity": capacity, "is_blocked": is_blocked}))
    await session.flush()


async def get_setting(session: AsyncSession, ctx: AdminContext, key: str) -> dict:
    require(ctx, Permission.MANAGE_SETTINGS)
    row = await session.get(SystemSetting, key)
    if row is None:
        raise NotFoundError("تنظیم یافت نشد.")
    return {"key": key, "value": row.value, "version": row.version}


async def update_setting(
    session: AsyncSession, ctx: AdminContext, key: str, value: object, expected_version: int
) -> dict:
    require(ctx, Permission.MANAGE_SETTINGS)
    clean = validate_setting(key, value)
    result = await session.execute(
        update(SystemSetting)
        .where(SystemSetting.key == key, SystemSetting.version == expected_version)
        .values(value=clean, version=SystemSetting.version + 1, updated_at=datetime.now(UTC))
    )
    if result.rowcount != 1:
        raise SettingsVersionConflictError("این تنظیم هم‌زمان تغییر کرده است. دوباره بخوانید و تلاش کنید.")
    session.add(AuditLog(actor_telegram_id=ctx.telegram_user_id, action="setting.updated",
                         entity_type="setting", entity_id=key, payload={"version": expected_version + 1}))
    await session.flush()
    return {"key": key, "version": expected_version + 1}


async def list_team(session: AsyncSession, ctx: AdminContext) -> list[dict]:
    require(ctx, Permission.COORDINATE)
    rows = (await session.execute(select(AdminUser).where(AdminUser.is_active.is_(True)))).scalars().all()
    return [{"telegram_user_id": a.telegram_user_id, "role": a.role, "display_name": a.display_name} for a in rows]
