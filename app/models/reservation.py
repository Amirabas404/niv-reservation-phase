from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("party_size > 0", name="ck_reservations_party_positive"),
        CheckConstraint("booking_end > booking_start", name="ck_reservations_time_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_code: Mapped[str] = mapped_column(String(20), unique=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id"))
    party_size: Mapped[int] = mapped_column(Integer)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    service_type: Mapped[str] = mapped_column(String(20), server_default=text("'dine_in'"))
    design: Mapped[str] = mapped_column(String(40), server_default=text("'none'"))
    with_cake: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(40))
    total_amount: Mapped[int] = mapped_column(Integer)
    price_snapshot: Mapped[Any] = mapped_column(JSONB, nullable=False)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    created_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
