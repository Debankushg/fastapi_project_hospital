from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.date_util import utc_now


async def find_by_id(s: AsyncSession, user_id: str) -> User | None:
    return await s.get(User, user_id)


async def find_by_email(s: AsyncSession, email: str) -> User | None:
    return await s.scalar(select(User).where(User.email == email.lower()))


async def create(s: AsyncSession, **values) -> User:
    """Inserts (flush only; the service commits). Emails are stored lower-cased."""
    user = User(**{**values, "email": values["email"].lower()})
    s.add(user)
    await s.flush()
    return user


def update(user: User, **values) -> User:
    """Applies the changes to the loaded user (written on the next flush/commit)."""
    for k, v in values.items():
        setattr(user, k, v)
    user.updated_at = utc_now()
    return user


async def delete(s: AsyncSession, user: User) -> None:
    await s.delete(user)


async def list_users(s: AsyncSession, roles: list[str] | None = None) -> list[User]:
    q = select(User)
    if roles is not None:
        q = q.where(User.role.in_(roles))
    return list((await s.scalars(q)).all())
