from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportTicket(Base):
    """One open conversation per customer at a time. Staff must claim it before replying."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'claimed', 'closed')", name="ck_support_tickets_status"),
        Index(
            "uq_support_active_customer",
            "customer_telegram_id",
            unique=True,
            postgresql_where=text("status <> 'closed'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_telegram_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    assigned_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(10))
    last_customer_message_id: Mapped[int | None] = mapped_column(Integer)


class SupportMessage(Base):
    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('customer', 'staff', 'system')", name="ck_support_messages_sender"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"))
    sender: Mapped[str] = mapped_column(String(10))
    sender_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
