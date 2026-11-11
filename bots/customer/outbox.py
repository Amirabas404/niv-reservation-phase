"""Delivers staff replies and system notices to customers through THIS bot (customers only receive
messages from a bot they have started)."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from bots.customer.backend_client import BackendClient

log = logging.getLogger(__name__)


async def deliver_outbox(bot: Bot, backend: BackendClient, interval: float = 3.0) -> None:
    while True:
        try:
            await _deliver_notifications(bot, backend)
            for item in await backend.outbox():
                text = item["text"]
                if item["sender"] == "staff":
                    text = "👩‍💼 پیام پشتیبانی NIV:\n\n" + text
                try:
                    await bot.send_message(item["customer_telegram_id"], text)
                except TelegramForbiddenError:
                    log.warning("customer blocked the bot; message %s dropped", item["id"])
                except TelegramAPIError:
                    log.exception("delivery failed for message %s; will retry", item["id"])
                    continue
                await backend.mark_delivered(item["id"])
        except Exception:  # noqa: BLE001 - keep the loop alive
            log.exception("outbox loop error")
        await asyncio.sleep(interval)


async def _deliver_notifications(bot: Bot, backend: BackendClient) -> None:
    for item in await backend.notifications():
        try:
            await bot.send_message(item["customer_telegram_id"], item["text"])
        except TelegramForbiddenError:
            log.warning("customer blocked the bot; notification %s dropped", item["id"])
        except TelegramAPIError:
            log.exception("notification %s failed; will retry", item["id"])
            continue
        await backend.notification_delivered(item["id"])
