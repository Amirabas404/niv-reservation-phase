"""Support conversations. Only one staff member may hold a ticket; automation is paused while claimed."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError, InvalidTransitionError, NoActiveTicketError, NotFoundError, PermissionDeniedError
from app.domain.permissions import Permission, Role
from app.models import AdminUser, AuditLog, SupportMessage, SupportTicket
from app.services.admin_service import AdminContext, require

MAX_TEXT = 2000
ACTIVE = ("open", "claimed")
SYSTEM_CLOSE_TEXT = "پیگیری شما پایان یافت. اگر سؤال دیگری دارید، همین‌جا پیام بدهید."


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise DomainError("متن پیام خالی است.")
    if len(cleaned) > MAX_TEXT:
        raise DomainError(f"متن پیام نباید بیش از {MAX_TEXT} نویسه باشد.")
    return cleaned


async def _active_for_customer(session: AsyncSession, telegram_user_id: int, for_update: bool = False) -> SupportTicket | None:
    stmt = select(SupportTicket).where(
        SupportTicket.customer_telegram_id == telegram_user_id, SupportTicket.status.in_(ACTIVE)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _ticket_for_update(session: AsyncSession, ticket_id: int) -> SupportTicket:
    t = (await session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())).scalar_one_or_none()
    if t is None:
        raise NotFoundError("گفتگو یافت نشد.")
    return t


def _audit(session: AsyncSession, actor: int | None, action: str, ticket_id: int, payload: dict) -> None:
    session.add(AuditLog(actor_telegram_id=actor, action=action, entity_type="support_ticket",
                         entity_id=str(ticket_id), payload=payload))


# ---------- customer side ----------

async def open_ticket(session: AsyncSession, *, telegram_user_id: int, reason: str) -> tuple[SupportTicket, bool]:
    existing = await _active_for_customer(session, telegram_user_id, for_update=True)
    if existing is not None:
        return existing, False
    ticket = SupportTicket(customer_telegram_id=telegram_user_id, reason=reason[:500],
                           status="open", opened_at=_now())
    try:
        async with session.begin_nested():
            session.add(ticket)
            await session.flush()
    except IntegrityError:
        existing = await _active_for_customer(session, telegram_user_id)
        if existing is not None:
            return existing, False
        raise
    return ticket, True


async def customer_message(session: AsyncSession, *, telegram_user_id: int, text: str) -> SupportTicket:
    ticket = await _active_for_customer(session, telegram_user_id, for_update=True)
    if ticket is None:
        raise NoActiveTicketError("گفتگوی فعالی برای شما وجود ندارد.")
    msg = SupportMessage(ticket_id=ticket.id, sender="customer", sender_telegram_id=telegram_user_id,
                         text=_clean(text), created_at=_now())
    session.add(msg)
    await session.flush()
    ticket.last_customer_message_id = msg.id
    return ticket


async def close_by_customer(session: AsyncSession, *, telegram_user_id: int) -> bool:
    ticket = await _active_for_customer(session, telegram_user_id, for_update=True)
    if ticket is None:
        return False
    ticket.status = "closed"
    ticket.closed_by = "customer"
    ticket.closed_at = _now()
    await session.flush()
    return True


# ---------- staff side ----------

async def claim(session: AsyncSession, ctx: AdminContext, ticket_id: int) -> SupportTicket:
    require(ctx, Permission.COORDINATE)
    t = await _ticket_for_update(session, ticket_id)
    if t.status == "closed":
        raise InvalidTransitionError("این گفتگو بسته شده است.")
    if t.status == "claimed":
        if t.assigned_telegram_id == ctx.telegram_user_id:
            return t
        raise InvalidTransitionError("این گفتگو توسط همکار دیگری پذیرفته شده است.")
    t.status = "claimed"
    t.assigned_telegram_id = ctx.telegram_user_id
    t.claimed_at = _now()
    _audit(session, ctx.telegram_user_id, "support.claimed", t.id, {})
    await session.flush()
    return t


async def reply(session: AsyncSession, ctx: AdminContext, ticket_id: int, text: str) -> None:
    require(ctx, Permission.COORDINATE)
    t = await _ticket_for_update(session, ticket_id)
    if t.status != "claimed" or t.assigned_telegram_id != ctx.telegram_user_id:
        raise PermissionDeniedError("این گفتگو به شما واگذار نشده است.")
    session.add(SupportMessage(ticket_id=t.id, sender="staff", sender_telegram_id=ctx.telegram_user_id,
                               text=_clean(text), created_at=_now()))
    await session.flush()


async def close(session: AsyncSession, ctx: AdminContext, ticket_id: int) -> None:
    require(ctx, Permission.COORDINATE)
    t = await _ticket_for_update(session, ticket_id)
    if t.status == "closed":
        return
    if t.assigned_telegram_id != ctx.telegram_user_id and ctx.role != Role.MANAGER:
        raise PermissionDeniedError("فقط پشتیبان مسئول یا مدیر می‌تواند این گفتگو را ببندد.")
    t.status = "closed"
    t.closed_by = "staff"
    t.closed_at = _now()
    session.add(SupportMessage(ticket_id=t.id, sender="system", sender_telegram_id=None,
                               text=SYSTEM_CLOSE_TEXT, created_at=_now()))
    _audit(session, ctx.telegram_user_id, "support.closed", t.id, {})
    await session.flush()


async def list_tickets(session: AsyncSession, ctx: AdminContext, statuses: list[str]) -> list[dict]:
    require(ctx, Permission.COORDINATE)
    stmt = (
        select(SupportTicket, AdminUser.display_name)
        .outerjoin(AdminUser, AdminUser.telegram_user_id == SupportTicket.assigned_telegram_id)
        .order_by(SupportTicket.id)
        .limit(100)
    )
    if statuses:
        stmt = stmt.where(SupportTicket.status.in_(statuses))
    rows = (await session.execute(stmt)).all()

    last_ids = [t.last_customer_message_id for t, _ in rows if t.last_customer_message_id]
    texts: dict[int, str] = {}
    if last_ids:
        for m in (await session.execute(select(SupportMessage).where(SupportMessage.id.in_(last_ids)))).scalars():
            texts[m.id] = m.text

    out = []
    for t, assignee_name in rows:
        last = None
        if t.last_customer_message_id:
            last = {"id": t.last_customer_message_id, "text": texts.get(t.last_customer_message_id, "")}
        out.append({
            "id": t.id,
            "status": t.status,
            "reason": t.reason,
            "customer_telegram_id": t.customer_telegram_id,
            "assigned_telegram_id": t.assigned_telegram_id,
            "assigned_name": assignee_name,
            "opened_at": t.opened_at.isoformat(),
            "last_customer_message": last,
        })
    return out


async def history(session: AsyncSession, ctx: AdminContext, ticket_id: int) -> list[dict]:
    require(ctx, Permission.COORDINATE)
    msgs = (await session.execute(
        select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.id).limit(200)
    )).scalars().all()
    return [{"sender": m.sender, "text": m.text, "created_at": m.created_at.isoformat()} for m in msgs]


async def report(session: AsyncSession, ctx: AdminContext) -> list[dict]:
    require(ctx, Permission.VIEW_SUPPORT_REPORT)
    rows = (await session.execute(
        select(SupportTicket.assigned_telegram_id, SupportTicket.status, SupportTicket.claimed_at,
               SupportTicket.closed_at, AdminUser.display_name)
        .outerjoin(AdminUser, AdminUser.telegram_user_id == SupportTicket.assigned_telegram_id)
        .where(SupportTicket.assigned_telegram_id.is_not(None))
    )).all()
    per: dict[int, dict] = {}
    for assignee, status, claimed_at, closed_at, name in rows:
        entry = per.setdefault(assignee, {"telegram_user_id": assignee, "name": name or "—",
                                          "claimed": 0, "closed": 0, "_minutes": []})
        entry["claimed"] += 1
        if status == "closed" and claimed_at and closed_at:
            entry["closed"] += 1
            entry["_minutes"].append((closed_at - claimed_at).total_seconds() / 60)
    result = []
    for e in per.values():
        mins = e.pop("_minutes")
        e["avg_minutes_to_close"] = round(sum(mins) / len(mins), 1) if mins else None
        result.append(e)
    return result


async def outbox(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        select(SupportMessage, SupportTicket.customer_telegram_id)
        .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
        .where(SupportMessage.sender.in_(["staff", "system"]), SupportMessage.delivered_at.is_(None))
        .order_by(SupportMessage.id)
        .limit(50)
    )).all()
    return [{"id": m.id, "sender": m.sender, "text": m.text, "customer_telegram_id": cid} for m, cid in rows]


async def mark_delivered(session: AsyncSession, message_id: int) -> None:
    msg = await session.get(SupportMessage, message_id)
    if msg is None:
        raise NotFoundError("پیام یافت نشد.")
    if msg.delivered_at is None:
        msg.delivered_at = _now()
        await session.flush()
