"""Minimal Telegram Bot API sender for the worker. Used only for scheduled reports to managers."""

import logging

import httpx

log = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, token: str) -> None:
        self._base = f"https://api.telegram.org/bot{token}"

    async def send_message(self, chat_id: int, text: str) -> bool:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{self._base}/sendMessage", json={"chat_id": chat_id, "text": text[:4000]})
        if r.status_code != 200:
            log.warning("sendMessage to %s failed: %s", chat_id, r.status_code)
            return False
        return True

    async def send_document(self, chat_id: int, data: bytes, filename: str, caption: str = "") -> bool:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self._base}/sendDocument",
                data={"chat_id": str(chat_id), "caption": caption[:1000]},
                files={"document": (filename, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        if r.status_code != 200:
            log.warning("sendDocument to %s failed: %s", chat_id, r.status_code)
            return False
        return True
