"""Watches the ticket queue and notifies staff. Runs inside the management bot process.

Uses NOTIFIER_ACTOR_TELEGRAM_ID (a manager) to read the team and queue. The first poll only records
the current state so restarts do not re-announce existing conversations.
"""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bots.management import keyboards as kb
from bots.management.backend import AdminBackend, AdminBackendError

log = logging.getLogger(__name__)


class TicketNotifier:
    def __init__(self, bot: Bot, backend: AdminBackend, actor_id: int) -> None:
        self._bot = bot
        self._backend = backend
        self._actor = actor_id
        self._seen_status: dict[int, str] = {}
        self._seen_message: dict[int, int] = {}
        self._initialized = False

    async def run(self, interval: float = 8.0) -> None:
        while True:
            try:
                await self.tick()
            except AdminBackendError as exc:
                log.warning("notifier backend error: %s", exc.message)
            except Exception:  # noqa: BLE001
                log.exception("notifier loop error")
            await asyncio.sleep(interval)

    async def _send(self, chat_id: int, text: str, markup=None) -> None:
        try:
            await self._bot.send_message(chat_id, text, reply_markup=markup)
        except TelegramAPIError:
            log.warning("could not notify staff %s (have they started the bot?)", chat_id)

    async def tick(self) -> None:
        tickets = await self._backend.tickets(self._actor, ["open", "claimed"])
        if not self._initialized:
            for t in tickets:
                self._seen_status[t["id"]] = t["status"]
                if t.get("last_customer_message"):
                    self._seen_message[t["id"]] = t["last_customer_message"]["id"]
            self._initialized = True
            return

        team = await self._backend.team(self._actor)
        for t in tickets:
            tid = t["id"]
            is_new = tid not in self._seen_status
            self._seen_status[tid] = t["status"]
            last = t.get("last_customer_message")
            new_message = bool(last) and last["id"] > self._seen_message.get(tid, 0)
            if last:
                self._seen_message[tid] = last["id"]

            if is_new and t["status"] == "open":
                text = "🔔 گفتگوی جدید پشتیبانی\n\n" + f"#{tid} · موضوع: {t['reason']}"
                for member in team:
                    await self._send(member["telegram_user_id"], text, kb.ticket_actions(t, -1))
            elif new_message:
                preview = f"💬 پیام جدید در گفتگو #{tid}:\n{last['text'][:300]}"
                if t["status"] == "claimed" and t["assigned_telegram_id"]:
                    await self._send(t["assigned_telegram_id"], preview, kb.ticket_actions(t, t["assigned_telegram_id"]))
                elif t["status"] == "open":
                    for member in team:
                        await self._send(member["telegram_user_id"], preview, kb.ticket_actions(t, -1))
