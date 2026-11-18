"""seed editable bank card setting

Revision ID: 0006_bank_card_setting
Revises: 0005_reports_jobs
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_bank_card_setting"
down_revision: Union[str, None] = "0005_reports_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO system_settings (key, value, version)
        VALUES ('bank_card', '{"card_number": "", "owner_name": ""}'::jsonb, 1)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'bank_card'")
