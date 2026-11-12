"""reports, notifications, job idempotency, reminder tracking

Revision ID: 0005_reports_jobs
Revises: 0004_support
Create Date: 2026-11-09
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_reports_jobs"
down_revision: Union[str, None] = "0004_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REPORTS = {"nightly_time": "22:00", "monthly_time": "23:00"}


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("job_name", sa.String(length=60), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_date", sa.Date(), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("payments", sa.Column("payment_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text("INSERT INTO system_settings (key, value, version) VALUES ('reports', CAST(:v AS jsonb), 1)")
        .bindparams(v=json.dumps(REPORTS))
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'reports'")
    op.drop_column("payments", "payment_reminder_sent_at")
    op.drop_table("daily_reports")
    op.drop_table("notifications")
    op.drop_table("job_runs")
