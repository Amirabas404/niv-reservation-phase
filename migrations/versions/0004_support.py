"""support tickets and messages

Revision ID: 0004_support
Revises: 0003_admin_rbac
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_support"
down_revision: Union[str, None] = "0003_admin_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(length=10), nullable=True),
        sa.Column("last_customer_message_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('open', 'claimed', 'closed')", name="ck_support_tickets_status"),
    )
    # At most one non-closed ticket per customer.
    op.create_index(
        "uq_support_active_customer",
        "support_tickets",
        ["customer_telegram_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'closed'"),
    )

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=False),
        sa.Column("sender", sa.String(length=10), nullable=False),
        sa.Column("sender_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("sender IN ('customer', 'staff', 'system')", name="ck_support_messages_sender"),
    )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_index("uq_support_active_customer", table_name="support_tickets")
    op.drop_table("support_tickets")
