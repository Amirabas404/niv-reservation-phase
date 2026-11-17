from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from unittest.mock import AsyncMock

from app.api.deps import get_session
from app.main import app
from app.models import Notification
from app.services import notification_service
from bots.customer.outbox import deliver_outbox_once


async def _client_for_session(session):
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_notification_api_lists_pending_and_marks_delivered(session):
    await notification_service.enqueue(
        session, telegram_user_id=7001, kind="reservation_update", text="رزرو شما تأیید شد."
    )
    await session.commit()
    notification = (await session.execute(
        select(Notification).where(Notification.customer_telegram_id == 7001)
    )).scalar_one()

    client = await _client_for_session(session)
    try:
        response = await client.get("/internal/notifications", headers={"X-Service-Token": "test-token"})
        assert response.status_code == 200
        assert {
            "id": notification.id,
            "customer_telegram_id": 7001,
            "kind": "reservation_update",
            "text": "رزرو شما تأیید شد.",
        } in response.json()

        delivered = await client.post(
            f"/internal/notifications/{notification.id}/delivered",
            headers={"X-Service-Token": "test-token"},
        )
        assert delivered.status_code == 204
        await session.refresh(notification)
        assert notification.delivered_at is not None
    finally:
        await client.aclose()
        app.dependency_overrides.pop(get_session, None)


async def test_notification_api_rejects_missing_service_token(session):
    client = await _client_for_session(session)
    try:
        response = await client.get("/internal/notifications")
        assert response.status_code == 401
    finally:
        await client.aclose()
        app.dependency_overrides.pop(get_session, None)


async def test_support_outbox_continues_when_notification_delivery_fails():
    bot = AsyncMock()
    backend = AsyncMock()
    backend.notifications.side_effect = RuntimeError("notifications API unavailable")
    backend.outbox.return_value = [
        {
            "id": 91,
            "customer_telegram_id": 7002,
            "sender": "staff",
            "text": "سلام، در خدمت شما هستیم.",
        }
    ]

    await deliver_outbox_once(bot, backend)

    bot.send_message.assert_awaited_once_with(
        7002, "👩‍💼 پیام پشتیبانی NIV:\n\nسلام، در خدمت شما هستیم."
    )
    backend.mark_delivered.assert_awaited_once_with(91)
