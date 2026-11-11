"""Operational CLI. Example:
    python -m app.cli add-admin --telegram-id 123456789 --role manager --name "سام"
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import engine
from app.models import AdminUser


async def add_admin(telegram_id: int, role: str, name: str) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        existing = (await session.execute(
            select(AdminUser).where(AdminUser.telegram_user_id == telegram_id)
        )).scalar_one_or_none()
        if existing:
            existing.role, existing.display_name, existing.is_active = role, name, True
        else:
            session.add(AdminUser(telegram_user_id=telegram_id, role=role, display_name=name))
        await session.commit()
    print(f"admin {telegram_id} saved with role={role}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="niv-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add-admin")
    add.add_argument("--telegram-id", type=int, required=True)
    add.add_argument("--role", choices=["manager", "support"], required=True)
    add.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.cmd == "add-admin":
        asyncio.run(add_admin(args.telegram_id, args.role, args.name))


if __name__ == "__main__":
    main()
