from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"), unique=True)
    amount_expected: Mapped[int] = mapped_column(Integer)
    amount_verified: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    receipt_storage_key: Mapped[str | None] = mapped_column(String(500))
    receipt_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    refund_amount: Mapped[int | None] = mapped_column(Integer)
    payment_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
