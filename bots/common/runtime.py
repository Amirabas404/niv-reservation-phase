"""Runs a bot in polling mode (development) or webhook mode (Railway production)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

log = logging.getLogger(__name__)


async def run_bot(
    bot: Bot,
    dp: Dispatcher,
    *,
    webhook_base_url: str | None,
    webhook_secret: str | None,
    path: str,
    port: int,
    background: list[Callable[[], Awaitable[None]]],
) -> None:
    tasks = [asyncio.create_task(factory()) for factory in background]
    allowed = dp.resolve_used_update_types()
    try:
        if webhook_base_url:
            if not webhook_secret:
                raise SystemExit("WEBHOOK_SECRET is required when WEBHOOK_BASE_URL is set")
            app = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=webhook_secret).register(app, path=path)
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", port).start()
            await bot.set_webhook(f"{webhook_base_url.rstrip('/')}{path}", secret_token=webhook_secret,
                                  allowed_updates=allowed)
            log.info("webhook mode on port %s at %s", port, path)
            try:
                await asyncio.Event().wait()
            finally:
                await runner.cleanup()
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            log.info("polling mode")
            await dp.start_polling(bot, allowed_updates=allowed)
    finally:
        for t in tasks:
            t.cancel()
