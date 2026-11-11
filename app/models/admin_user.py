from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminUser(Base):
    """Staff authorized to use the management bot. Identity is the Telegram User ID, never the username."""

    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("role IN ('manager', 'support')", name="ck_admin_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
