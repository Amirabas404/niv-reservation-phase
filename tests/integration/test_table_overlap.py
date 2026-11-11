from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.domain.errors import TableConflictError
from app.models import Table
from app.services.reservation_service import confirm_reservation, create_reservation

UTC = ZoneInfo("UTC")


async def test_same_table_cannot_be_double_booked(session):
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    start = datetime(2026, 11, 10, 10, 30, tzinfo=UTC)
    r1 = await create_reservation(session, now=now, customer_name="علی رضایی", phone="09120000001",
                                  space_code="hall", party_size=2, booking_start=start)
    r2 = await create_reservation(session, now=now, customer_name="مریم احمدی", phone="09120000002",
                                  space_code="hall", party_size=2, booking_start=start)
    await session.commit()
    table = (await session.execute(select(Table).where(Table.number == "2"))).scalar_one()
    table.capacity = 4
    await session.commit()
    await confirm_reservation(session, public_code=r1.public_code, table_ids=[table.id], actor_telegram_id=1)
    await session.commit()
    with pytest.raises(TableConflictError):
        await confirm_reservation(session, public_code=r2.public_code, table_ids=[table.id], actor_telegram_id=1)
