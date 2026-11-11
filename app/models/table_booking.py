from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TableBooking(Base):
    """Occupancy of a table in a time range. Overlaps are prevented by a PostgreSQL
    EXCLUDE constraint (see migration 0002), not only by application code."""

    __tablename__ = "table_bookings"
    __table_args__ = (
        CheckConstraint("kind IN ('reservation', 'block')", name="ck_table_bookings_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"))
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"))
    booking_range: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), server_default=text("'reservation'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
