"""Worker process: reminders, unpaid expiry, nightly report, monthly export.

Run as its own service:  python -m app.worker.main
It shares the database and the codebase with the Backend but holds no HTTP endpoints.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.db.session import engine
from app.integrations.telegram_sender import TelegramSender
from app.worker.jobs import run_scheduled

TICK_SECONDS = 60


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    log = logging.getLogger("worker")

    if not settings.management_bot_token:
        raise SystemExit("MANAGEMENT_BOT_TOKEN is required: scheduled reports are sent through the management bot")
    sender = TelegramSender(settings.management_bot_token.get_secret_value())
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    log.info("worker started (tick=%ss, tz=%s)", TICK_SECONDS, settings.timezone)
    while True:
        try:
            await run_scheduled(session_maker, sender, datetime.now(UTC))
        except Exception:  # noqa: BLE001 - never let one failed tick stop the worker
            log.exception("worker tick failed")
        await asyncio.sleep(TICK_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
