from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PatientProfile


def create(s: AsyncSession, **values) -> PatientProfile:
    profile = PatientProfile(**values)
    s.add(profile)
    return profile


async def upsert(s: AsyncSession, user_id: str, fields: dict) -> None:
    """Creates the profile if missing, otherwise updates only the given fields."""
    await s.execute(
        insert(PatientProfile)
        .values(user_id=user_id, **fields)
        .on_conflict_do_update(index_elements=[PatientProfile.user_id], set_=fields)
    )
