"""Management bot entry point. Polling in development; webhook in production (set WEBHOOK_BASE_URL)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bots.common.runtime import run_bot
from bots.management.backend import AdminBackend
from bots.management.config import get_management_settings
from bots.management.handlers import router
from bots.management.notifier import TicketNotifier

WEBHOOK_PATH = "/webhook/management"


async def main() -> None:
    settings = get_management_settings()
    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.management_bot_token.get_secret_value())
    storage = RedisStorage.from_url(settings.redis_url)
    backend = AdminBackend(settings.management_bot_backend_url, settings.admin_service_token.get_secret_value())
    notifier = TicketNotifier(bot, backend, settings.notifier_actor_telegram_id)

    dp = Dispatcher(storage=storage)
    dp["backend"] = backend
    dp.include_router(router)
    try:
        await run_bot(
            bot,
            dp,
            webhook_base_url=settings.webhook_base_url,
            webhook_secret=settings.webhook_secret.get_secret_value() if settings.webhook_secret else None,
            path=WEBHOOK_PATH,
            port=settings.port,
            background=[notifier.run],
        )
    finally:
        await backend.close()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
