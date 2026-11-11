"""Builds the monthly workbook and stores a copy privately. Used by the worker and the admin API."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config_helpers import storage_for_reports
from app.integrations.excel import build_monthly_workbook
from app.services.reporting_service import monthly_rows, monthly_summary


async def export_monthly(session: AsyncSession, year: int, month: int) -> tuple[bytes, str, dict]:
    rows = await monthly_rows(session, year, month)
    summary = await monthly_summary(session, year, month)
    ym = f"{year}-{month:02d}"
    data = build_monthly_workbook(rows, summary, ym)
    storage = storage_for_reports()
    await storage.save_named(f"reports/monthly/{ym}.xlsx", data)
    return data, f"NIV-monthly-{ym}.xlsx", summary
