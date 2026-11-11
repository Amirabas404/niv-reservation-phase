from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import admin_context
from app.api.deps import get_session, require_service_token
from app.domain.calendar_rules import parse_year_month
from app.domain.errors import PermissionDeniedError
from app.domain.permissions import Permission
from app.excel_export import export_monthly
from app.services import admin_service
from app.services import notification_service as notes
from app.services.reporting_service import daily_report

internal_router = APIRouter(prefix="/internal", tags=["notifications"], dependencies=[Depends(require_service_token)])
admin_router = APIRouter(prefix="/admin/reports", tags=["reports"])


@internal_router.get("/notifications")
async def pending_notifications(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await notes.pending(session)


@internal_router.post("/notifications/{notification_id}/delivered", status_code=204)
async def delivered(notification_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    await notes.mark_delivered(session, notification_id)
    await session.commit()
    return Response(status_code=204)


@admin_router.get("/daily")
async def daily(
    day: date | None = Query(default=None),
    ctx: admin_service.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    admin_service.require(ctx, Permission.VIEW_REPORTS)
    target = day or datetime.now(ZoneInfo(get_settings().timezone)).date()
    return await daily_report(session, target)


@admin_router.get("/monthly.xlsx")
async def monthly(
    ym: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    ctx: admin_service.AdminContext = Depends(admin_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    admin_service.require(ctx, Permission.VIEW_REPORTS)
    try:
        year, month = parse_year_month(ym)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ماه نامعتبر است.") from exc
    data, filename, _ = await export_monthly(session, year, month)
    await session.commit()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
