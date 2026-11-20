from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import TableBooking
from app.services.reservation_service import confirm_reservation, create_reservation

UTC = ZoneInfo("UTC")


async def test_manager_confirmation_no_longer_requires_table_assignment(session):
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    start = datetime(2026, 11, 10, 10, 30, tzinfo=UTC)
    r1 = await create_reservation(session, now=now, customer_name="علی رضایی", phone="09120000001",
                                  space_code="hall", party_size=2, booking_start=start)
    r2 = await create_reservation(session, now=now, customer_name="مریم احمدی", phone="09120000002",
                                  space_code="hall", party_size=2, booking_start=start)
    await session.commit()
    await confirm_reservation(session, public_code=r1.public_code, table_ids=[], actor_telegram_id=1)
    await session.commit()
    await confirm_reservation(session, public_code=r2.public_code, table_ids=[], actor_telegram_id=1)
    await session.commit()
    bookings = (await session.execute(select(TableBooking))).scalars().all()
    assert bookings == []
