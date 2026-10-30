import asyncio

import bcrypt

from app.config.constants import BCRYPT_ROUNDS


# bcrypt only reads the first 72 bytes (bcryptjs truncates silently; newer bcrypt libs raise), so cut here.
def _pw(plain: str) -> bytes:
    return plain.encode()[:72]


def _hash_sync(plain: str) -> str:
    return bcrypt.hashpw(_pw(plain), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def _verify_sync(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw(plain), hashed.encode())
    except ValueError:
        return False


# bcrypt is deliberately slow (~250 ms), so it runs in a worker thread instead of blocking the event loop.
async def hash_password(plain: str) -> str:
    return await asyncio.to_thread(_hash_sync, plain)


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_sync, plain, hashed)


# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = _hash_sync("dummy-password-for-timing")
