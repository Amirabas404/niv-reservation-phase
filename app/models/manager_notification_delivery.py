from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, BigInteger, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ManagerNotificationDelivery(Base):
    __tablename__ = "manager_notification_deliveries"
    __table_args__ = (UniqueConstraint("notification_id", "telegram_user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("manager_notifications.id", ondelete="CASCADE"), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
