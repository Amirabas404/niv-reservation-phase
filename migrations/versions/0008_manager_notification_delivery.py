"""track manager notification delivery per recipient

Revision ID: 0008_manager_notification_delivery
Revises: 0007_manager_notifications
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008_notify_delivery"
down_revision: Union[str, None] = "0007_manager_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "manager_notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("manager_notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notification_id", "telegram_user_id"),
    )

def downgrade() -> None:
    op.drop_table("manager_notification_deliveries")
