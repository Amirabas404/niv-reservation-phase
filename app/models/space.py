from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Space(Base):
    __tablename__ = "spaces"
    __table_args__ = (UniqueConstraint("branch_id", "code", name="uq_spaces_branch_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
