"""Daily PostgreSQL backup to private storage, with retention.

Requires the pg_dump client matching the server major version (see Dockerfile).
The password is passed through PGPASSWORD, never on the command line.
"""

import asyncio
import gzip
import logging
import os
from datetime import date, timedelta

from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.integrations.storage import get_storage

log = logging.getLogger(__name__)
PREFIX = "backups/"


async def dump_database(settings: Settings) -> bytes:
    url = make_url(settings.database_url.replace("+asyncpg", ""))
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    cmd = ["pg_dump", "--no-owner", "--no-privileges", "--format=plain",
           "-h", url.host or "localhost", "-p", str(url.port or 5432),
           "-U", url.username or "postgres", url.database or ""]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE, env=env)
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed ({proc.returncode}): {err.decode(errors='replace')[:300]}")
    return out


def _key_date(key: str) -> date | None:
    try:
        return date.fromisoformat(key.rsplit("/", 1)[-1].removeprefix("niv-").split(".")[0])
    except ValueError:
        return None


async def apply_retention(keep_days: int, today: date) -> int:
    storage = get_storage()
    removed = 0
    for key in await storage.list_keys(PREFIX):
        d = _key_date(key)
        if d is not None and d < today - timedelta(days=keep_days):
            await storage.delete(key)
            removed += 1
    return removed


async def run_backup(settings: Settings, local_day: date) -> str:
    raw = await dump_database(settings)
    compressed = gzip.compress(raw)
    key = f"{PREFIX}niv-{local_day.isoformat()}.sql.gz"
    await get_storage().save_named(key, compressed, "application/gzip")
    removed = await apply_retention(settings.backup_retention_days, local_day)
    log.info("backup %s stored (%d bytes); %d old backups removed", key, len(compressed), removed)
    return key
