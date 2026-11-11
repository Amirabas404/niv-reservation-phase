from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import admin_context
from app.api.deps import get_session, require_service_token
from app.domain.errors import NoActiveTicketError
from app.schemas.support import SupportCustomerIdIn, SupportCustomerMessageIn, SupportOpenIn, SupportReplyIn
from app.services import admin_service
from app.services import support_service as svc

internal_router = APIRouter(prefix="/internal/support", tags=["support-internal"],
                            dependencies=[Depends(require_service_token)])
admin_router = APIRouter(prefix="/admin", tags=["support-admin"])


# ---------- customer bot (service token) ----------

@internal_router.post("/open")
async def open_support(body: SupportOpenIn, session: AsyncSession = Depends(get_session)) -> dict:
    ticket, created = await svc.open_ticket(session, telegram_user_id=body.telegram_user_id, reason=body.reason)
    await session.commit()
    return {"ticket_id": ticket.id, "status": ticket.status, "is_new": created}


@internal_router.post("/messages", status_code=204)
async def customer_message(body: SupportCustomerMessageIn, session: AsyncSession = Depends(get_session)) -> Response:
    await svc.customer_message(session, telegram_user_id=body.telegram_user_id, text=body.text)
    await session.commit()
    return Response(status_code=204)


@internal_router.post("/close")
async def close_support(body: SupportCustomerIdIn, session: AsyncSession = Depends(get_session)) -> dict:
    closed = await svc.close_by_customer(session, telegram_user_id=body.telegram_user_id)
    await session.commit()
    return {"closed": closed}


@internal_router.get("/outbox")
async def outbox(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await svc.outbox(session)


@internal_router.post("/outbox/{message_id}/delivered", status_code=204)
async def delivered(message_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    await svc.mark_delivered(session, message_id)
    await session.commit()
    return Response(status_code=204)


# ---------- staff (management bot, RBAC) ----------

@admin_router.get("/team")
async def team(ctx: admin_service.AdminContext = Depends(admin_context),
               session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await admin_service.list_team(session, ctx)


@admin_router.get("/support/tickets")
async def tickets(status: list[str] = Query(default=[]),
                  ctx: admin_service.AdminContext = Depends(admin_context),
                  session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await svc.list_tickets(session, ctx, status)


@admin_router.post("/support/tickets/{ticket_id}/claim")
async def claim(ticket_id: int, ctx: admin_service.AdminContext = Depends(admin_context),
                session: AsyncSession = Depends(get_session)) -> dict:
    t = await svc.claim(session, ctx, ticket_id)
    await session.commit()
    return {"ticket_id": t.id, "status": t.status}


@admin_router.post("/support/tickets/{ticket_id}/reply", status_code=204)
async def staff_reply(ticket_id: int, body: SupportReplyIn,
                      ctx: admin_service.AdminContext = Depends(admin_context),
                      session: AsyncSession = Depends(get_session)) -> Response:
    await svc.reply(session, ctx, ticket_id, body.text)
    await session.commit()
    return Response(status_code=204)


@admin_router.post("/support/tickets/{ticket_id}/close", status_code=204)
async def staff_close(ticket_id: int, ctx: admin_service.AdminContext = Depends(admin_context),
                      session: AsyncSession = Depends(get_session)) -> Response:
    await svc.close(session, ctx, ticket_id)
    await session.commit()
    return Response(status_code=204)


@admin_router.get("/support/tickets/{ticket_id}/messages")
async def ticket_history(ticket_id: int, ctx: admin_service.AdminContext = Depends(admin_context),
                         session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await svc.history(session, ctx, ticket_id)


@admin_router.get("/support/report")
async def support_report(ctx: admin_service.AdminContext = Depends(admin_context),
                         session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await svc.report(session, ctx)
