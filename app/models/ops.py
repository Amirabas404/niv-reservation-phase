from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobRun(Base):
    """Idempotency record. A scheduled job runs once per run_key (e.g. 'nightly:2026-11-09')."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_key: Mapped[str] = mapped_column(String(120), unique=True)
    job_name: Mapped[str] = mapped_column(String(60))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """Outgoing message to a customer, delivered by the customer bot."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_telegram_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, unique=True)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
