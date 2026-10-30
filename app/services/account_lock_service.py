from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import LOCK_MINUTES, MAX_FAILED_ATTEMPTS
from app.models import User
from app.repositories import user_repository
from app.utils.date_util import utc_now
from app.utils.http_error_util import HttpError


def assert_not_locked(user: User) -> None:
    if user.locked_until and user.locked_until > utc_now():
        raise HttpError(423, "Account temporarily locked. Try again later.")


async def record_failure(s: AsyncSession, user: User) -> None:
    """Counts a failed password/MFA attempt and locks the account once the limit is reached."""
    attempts = user.failed_attempts + 1
    lock = attempts >= MAX_FAILED_ATTEMPTS
    user_repository.update(
        user,
        failed_attempts=0 if lock else attempts,
        locked_until=utc_now() + timedelta(minutes=LOCK_MINUTES) if lock else user.locked_until,
    )
    await s.commit()


async def reset(s: AsyncSession, user: User) -> None:
    user_repository.update(user, failed_attempts=0, locked_until=None)
    await s.commit()
