"""Creates the first super admin from SUPER_ADMIN_* in .env.

    python -m app.db.seed
"""

import asyncio

from app.config import settings
from app.db import SessionLocal, engine
from app.repositories import user_repository
from app.utils.password_util import hash_password


async def main() -> None:
    if not settings.SUPER_ADMIN_EMAIL or not settings.SUPER_ADMIN_PASSWORD:
        raise SystemExit("Set SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD in .env")
    async with SessionLocal() as s:
        if await user_repository.find_by_email(s, settings.SUPER_ADMIN_EMAIL):
            print("Super admin already exists:", settings.SUPER_ADMIN_EMAIL)
            return
        await user_repository.create(
            s,
            email=settings.SUPER_ADMIN_EMAIL,
            full_name=settings.SUPER_ADMIN_NAME,
            password_hash=await hash_password(settings.SUPER_ADMIN_PASSWORD),
            role="super_admin",
        )
        await s.commit()
        print("Super admin created:", settings.SUPER_ADMIN_EMAIL, "(MFA setup is required on first login)")


async def run() -> None:
    try:
        await main()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
