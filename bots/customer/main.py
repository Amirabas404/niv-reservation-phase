"""Customer bot entry point. Polling in development; webhook in production (set WEBHOOK_BASE_URL)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from bots.common.runtime import run_bot
from bots.customer.backend_client import BackendClient
from bots.customer.config import get_bot_settings
from bots.customer.handlers import router
from bots.customer.outbox import deliver_outbox

WEBHOOK_PATH = "/webhook/customer"


async def main() -> None:
    settings = get_bot_settings()
    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.customer_bot_token.get_secret_value())
    storage = RedisStorage.from_url(settings.redis_url)
    backend = BackendClient(settings.backend_url, settings.internal_service_token.get_secret_value())

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
            background=[lambda: deliver_outbox(bot, backend)],
        )
    finally:
        await backend.close()
        await storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
