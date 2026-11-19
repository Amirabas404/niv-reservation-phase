"""Allow manager-approved overlapping table assignments.

Revision ID: 0009_manager_controls_table_overlap
Revises: 0008_notify_delivery
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009_manager_table_overlap"
down_revision: Union[str, None] = "0008_notify_delivery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Time conflicts are a manager decision; retain the booking records but remove
    # the database exclusion rule that previously rejected overlapping assignments.
    op.execute("ALTER TABLE table_bookings DROP CONSTRAINT IF EXISTS ex_table_bookings_no_overlap")


def downgrade() -> None:
    # Reinstating the constraint can fail if managers have approved overlaps.
    # Do not silently delete or rewrite booking history.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM table_bookings a
                JOIN table_bookings b
                  ON a.table_id = b.table_id
                 AND a.id < b.id
                 AND a.is_active AND b.is_active
                 AND a.booking_range && b.booking_range
            ) THEN
                ALTER TABLE table_bookings
                ADD CONSTRAINT ex_table_bookings_no_overlap
                EXCLUDE USING gist (table_id WITH =, booking_range WITH &&)
                WHERE (is_active);
            END IF;
        END $$;
        """
    )
