"""Re-encrypts every stored MFA secret from the current MFA_ENCRYPTION_KEY (.env) to a new key.

  1. openssl rand -hex 32                                              -> your new key
  2. NEW_MFA_ENCRYPTION_KEY=<new> python -m app.scripts.rotate_mfa_key           (dry run: only checks)
  3. NEW_MFA_ENCRYPTION_KEY=<new> python -m app.scripts.rotate_mfa_key --apply   (re-encrypts, one transaction)
  4. Put the new key into .env as MFA_ENCRYPTION_KEY and restart the server.

Back up the database first. Do not change .env before step 3, or existing MFA secrets become unreadable.
"""

import asyncio
import os
import re
import sys

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, engine
from app.models import User
from app.utils.crypto_util import decrypt_with_key, encrypt_with_key


async def main() -> None:
    old_key = settings.MFA_ENCRYPTION_KEY
    new_key = os.environ.get("NEW_MFA_ENCRYPTION_KEY", "")
    apply = "--apply" in sys.argv

    if not re.fullmatch(r"[0-9a-fA-F]{64}", new_key):
        raise SystemExit("Set NEW_MFA_ENCRYPTION_KEY to 64 hex chars (openssl rand -hex 32)")
    if new_key.lower() == old_key.lower():
        raise SystemExit("The new key is the same as the current key")
    if re.fullmatch(r"0+", new_key):
        raise SystemExit("Refusing an all-zeros key")

    async with SessionLocal() as s:
        users = list((await s.scalars(select(User).where(User.mfa_secret_enc.is_not(None)))).all())

        # Decrypt everything with the old key first, so nothing is written if any secret is unreadable.
        plain = {}
        for u in users:
            try:
                plain[u.id] = decrypt_with_key(u.mfa_secret_enc, old_key)
            except Exception:  # noqa: BLE001
                raise SystemExit(f"Cannot decrypt the secret of {u.email} with the current key. Is .env still the original key?")
        print(f"{len(plain)} MFA secret(s) readable with the current key.")

        if not apply:
            return print("Dry run only. Re-run with --apply to re-encrypt.")

        for u in users:
            u.mfa_secret_enc = encrypt_with_key(plain[u.id], new_key)
        await s.commit()  # one transaction
        print(f"Re-encrypted {len(plain)} secret(s). Now set MFA_ENCRYPTION_KEY in .env to the new key and restart.")


async def run() -> None:
    try:
        await main()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
