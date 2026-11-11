from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Table(Base):
    """A physical table. capacity stays NULL until the manager sets it; NULL means not bookable."""

    __tablename__ = "tables"
    __table_args__ = (
        UniqueConstraint("space_id", "number", name="uq_tables_space_number"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_tables_capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("spaces.id"))
    number: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
