"""add durable manager notification outbox

Revision ID: 0007_manager_notifications
Revises: 0006_bank_card_setting
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007_manager_notifications"
down_revision: Union[str, None] = "0006_bank_card_setting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "manager_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("manager_notifications")
