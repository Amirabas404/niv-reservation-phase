from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.lookup import router as lookup_router
from app.api.reports import admin_router as reports_admin_router
from app.api.reports import internal_router as reports_internal_router
from app.api.support import admin_router as support_admin_router
from app.api.support import internal_router as support_internal_router
from app.api.reservations import router as reservations_router
from app.db.session import engine
from app.domain.errors import DomainError

app = FastAPI(title="NIV Reservation Backend", version="0.2.0")
app.include_router(reservations_router)
app.include_router(lookup_router)
app.include_router(admin_router)
app.include_router(support_internal_router)
app.include_router(support_admin_router)
app.include_router(reports_internal_router)
app.include_router(reports_admin_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "support_offer": exc.support_offer},
    )


@app.get("/healthz")
async def healthz() -> JSONResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse({"status": "degraded", "database": "down"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return JSONResponse({"status": "ok", "database": "up"})
