from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def enqueue(session: AsyncSession, *, telegram_user_id: int, kind: str, text: str) -> None:
    session.add(Notification(customer_telegram_id=telegram_user_id, kind=kind, text=text,
                             created_at=datetime.now(UTC)))
    await session.flush()


async def pending(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        select(Notification).where(Notification.delivered_at.is_(None)).order_by(Notification.id).limit(50)
    )).scalars().all()
    return [{"id": n.id, "customer_telegram_id": n.customer_telegram_id, "kind": n.kind, "text": n.text} for n in rows]


async def mark_delivered(session: AsyncSession, notification_id: int) -> None:
    n = await session.get(Notification, notification_id)
    if n is not None and n.delivered_at is None:
        n.delivered_at = datetime.now(UTC)
        await session.flush()
