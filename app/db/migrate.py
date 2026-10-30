"""Creates the enum types and tables that do not exist yet (safe to re-run; never alters existing tables).

    python -m app.db.migrate
"""

import asyncio

from sqlalchemy import text

from app.db import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        # gen_random_uuid() is built in since Postgres 13; older servers need pgcrypto.
        await conn.execute(text("create extension if not exists pgcrypto"))
        await conn.run_sync(Base.metadata.create_all)
    print("Migrations applied")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
