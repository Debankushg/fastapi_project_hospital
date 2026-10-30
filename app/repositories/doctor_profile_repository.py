from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DoctorProfile, User


async def find_by_user(s: AsyncSession, user_id: str) -> DoctorProfile | None:
    return await s.get(DoctorProfile, user_id)


def create(s: AsyncSession, **values) -> DoctorProfile:
    profile = DoctorProfile(**values)
    s.add(profile)
    return profile


async def list_active(s: AsyncSession, specialty: str | None = None) -> list[dict]:
    """Active doctors joined with their user record, optionally filtered by specialty."""
    q = (
        select(User.id, User.full_name, DoctorProfile.specialty, DoctorProfile.consultation_fee)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .where(User.is_active.is_(True))
    )
    if specialty:
        q = q.where(DoctorProfile.specialty == specialty)
    return [
        {"id": r.id, "fullName": r.full_name, "specialty": r.specialty, "consultationFee": r.consultation_fee}
        for r in (await s.execute(q)).all()
    ]
