import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_URL = os.environ.get("TEST_DATABASE_URL")
TRUNCATE_SQL = (
    "TRUNCATE table_bookings, payments, reservations, customers, audit_logs, "
    "support_messages, support_tickets, notifications, job_runs, daily_reports "
    "RESTART IDENTITY CASCADE"
)


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    os.environ["DATABASE_URL"] = TEST_URL
    os.environ["PRIVATE_STORAGE_DIR"] = str(tmp_path_factory.mktemp("private"))
    get_settings.cache_clear()
    command.downgrade(Config("alembic.ini"), "base")
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture
async def session(migrated_db):
    engine = create_async_engine(TEST_URL)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        await s.execute(text(TRUNCATE_SQL))
        await s.execute(text("UPDATE tables SET capacity = NULL, is_blocked = false"))
        await s.commit()
        yield s
    await engine.dispose()
