"""booking core: spaces, tables, customers, reservations, table bookings, payments, audit

Revision ID: 0002_booking_core
Revises: 0001_initial
Create Date: 2026-11-09
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_booking_core"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRICING = {
    "per_person": {"hall": 39000, "roof_family": 39000, "roof_smoke_free": 39000},
    "vip_flat_up_to_4": 259000,
    "vip_flat_5_to_10": 390000,
    "vip_max_party": 10,
    "designs": {"dried_flower_candle": 259000, "balloon_stand": 129000, "both": 388000},
    "catering_per_person": 39000,
}

RULES = {
    "dine_in_open": "07:30",
    "dine_in_close": "23:30",
    "design_min_lead_hours": 5,
    "cancellation_cutoff_hours": 8,
    # ASSUMPTIONS to confirm with owner:
    "reservation_duration_minutes": 120,
    "payment_reminder_hours_before": 8,
    "payment_deadline_hours_before": 7,
    "refund_percent": 50,
}

SPACES = [
    ("hall", "سالن پایین"),
    ("roof_family", "روف‌گاردن خانوادگی"),
    ("roof_smoke_free", "روف‌گاردن فری اسموک"),
    ("vip", "VIP"),
]

TABLE_NUMBERS = {
    "hall": [str(n) for n in range(2, 11)],
    "roof_family": [str(n) for n in range(14, 26)],
    "roof_smoke_free": [str(n) for n in range(30, 44)],
    "vip": ["VIP-1"],
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("branch_id", "code", name="uq_spaces_branch_code"),
    )

    op.create_table(
        "tables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id"), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("space_id", "number", name="uq_tables_space_number"),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name="ck_tables_capacity_positive"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False, unique=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id"), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_type", sa.String(length=20), server_default=sa.text("'dine_in'"), nullable=False),
        sa.Column("design", sa.String(length=40), server_default=sa.text("'none'"), nullable=False),
        sa.Column("with_cake", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("price_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("party_size > 0", name="ck_reservations_party_positive"),
        sa.CheckConstraint("booking_end > booking_start", name="ck_reservations_time_order"),
    )

    op.create_table(
        "table_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("tables.id"), nullable=False),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id"), nullable=True),
        sa.Column("booking_range", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default=sa.text("'reservation'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('reservation', 'block')", name="ck_table_bookings_kind"),
    )
    # Database-level guarantee: no two ACTIVE bookings may overlap on the same table.
    op.execute(
        """
        ALTER TABLE table_bookings
        ADD CONSTRAINT ex_table_bookings_no_overlap
        EXCLUDE USING gist (table_id WITH =, booking_range WITH &&)
        WHERE (is_active)
        """
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id"), nullable=False, unique=True),
        sa.Column("amount_expected", sa.Integer(), nullable=False),
        sa.Column("amount_verified", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("receipt_storage_key", sa.String(length=500), nullable=True),
        sa.Column("receipt_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Seed: spaces and tables (capacity intentionally NULL until the manager sets it).
    for code, name in SPACES:
        op.execute(
            sa.text(
                "INSERT INTO spaces (branch_id, code, name, is_active) "
                "SELECT id, :code, :name, true FROM branches WHERE code = 'NIV-01'"
            ).bindparams(code=code, name=name)
        )
    for space_code, numbers in TABLE_NUMBERS.items():
        for number in numbers:
            op.execute(
                sa.text(
                    "INSERT INTO tables (space_id, number, capacity, is_blocked, is_active) "
                    "SELECT s.id, :number, NULL, false, true FROM spaces s "
                    "JOIN branches b ON b.id = s.branch_id "
                    "WHERE b.code = 'NIV-01' AND s.code = :space_code"
                ).bindparams(number=number, space_code=space_code)
            )

    # Seed: business settings. Card details are deliberately NOT seeded; the manager sets them.
    for key, value in (("pricing", PRICING), ("rules", RULES)):
        op.execute(
            sa.text(
                "INSERT INTO system_settings (key, value, version) "
                "VALUES (:key, CAST(:value AS jsonb), 1)"
            ).bindparams(key=key, value=json.dumps(value, ensure_ascii=False))
        )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("payments")
    op.execute("ALTER TABLE table_bookings DROP CONSTRAINT IF EXISTS ex_table_bookings_no_overlap")
    op.drop_table("table_bookings")
    op.drop_table("reservations")
    op.drop_table("customers")
    op.drop_table("tables")
    op.drop_table("spaces")
    op.execute("DELETE FROM system_settings WHERE key IN ('pricing', 'rules')")
