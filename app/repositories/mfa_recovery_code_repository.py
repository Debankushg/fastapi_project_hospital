from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MfaRecoveryCode
from app.utils.date_util import utc_now


async def delete_all_for_user(s: AsyncSession, user_id: str) -> None:
    await s.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))


async def replace_for_user(s: AsyncSession, user_id: str, code_hashes: list[str]) -> None:
    """Replaces all of a user's recovery codes with the given hashes."""
    await delete_all_for_user(s, user_id)
    s.add_all(MfaRecoveryCode(user_id=user_id, code_hash=h) for h in code_hashes)


async def consume(s: AsyncSession, user_id: str, code_hash: str) -> bool:
    """Atomically marks an unused code as used. Returns False if it does not exist or was already used."""
    result = await s.execute(
        update(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.user_id == user_id,
            MfaRecoveryCode.code_hash == code_hash,
            MfaRecoveryCode.used_at.is_(None),
        )
        .values(used_at=utc_now())
        .returning(MfaRecoveryCode.id)
    )
    return result.first() is not None
