"""Dev helper: prints the current MFA code for an account, so you can sign in without an authenticator app.

    python -m app.scripts.mfa_code user@example.com          prints the current code
    python -m app.scripts.mfa_code user@example.com --key    also prints the setup key

Reads the encrypted secret with the server's MFA_ENCRYPTION_KEY, so it only works for someone with
access to the server. Refuses to run in production.
"""

import asyncio
import sys
import time

import pyotp

from app.config import settings
from app.db import SessionLocal, engine
from app.utils.crypto_util import decrypt
from app.repositories import user_repository


async def main() -> None:
    if settings.NODE_ENV == "production":
        raise SystemExit("Disabled in production")
    email = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not email:
        raise SystemExit("Usage: python -m app.scripts.mfa_code <email> [--key]")

    async with SessionLocal() as s:
        user = await user_repository.find_by_email(s, email)
    if not user or not user.mfa_secret_enc:
        raise SystemExit(f"No MFA secret for {email}. Finish MFA setup first.")

    secret = decrypt(user.mfa_secret_enc)
    print(f"{user.email}{'' if user.mfa_enabled else ' (MFA setup not confirmed yet)'}")
    if "--key" in sys.argv:
        print(f"Key:  {secret}")
    print(f"Code: {pyotp.TOTP(secret).now()}   (valid for ~{30 - int(time.time()) % 30}s)")


async def run() -> None:
    try:
        await main()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
