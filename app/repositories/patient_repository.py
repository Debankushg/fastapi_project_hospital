from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PatientProfile, User
from app.utils.pagination_util import like_pattern


async def search(
    s: AsyncSession, *, search: str | None, sort_by: str, order: str, limit: int, offset: int
) -> tuple[list[tuple[User, PatientProfile | None]], int]:
    """Paginated, searchable patient list (account + profile)."""
    cond = [User.role == "patient"]
    if search:
        p = like_pattern(search)
        cond.append(
            or_(
                User.full_name.ilike(p, escape="\\"),
                User.email.ilike(p, escape="\\"),
                User.phone.ilike(p, escape="\\"),
            )
        )
    col = User.created_at if sort_by == "joined" else User.full_name
    rows = (
        await s.execute(
            select(User, PatientProfile)
            .outerjoin(PatientProfile, PatientProfile.user_id == User.id)
            .where(*cond)
            .order_by(col.asc() if order == "asc" else col.desc(), User.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await s.scalar(select(func.count()).select_from(User).where(*cond))
    return [(u, p) for u, p in rows], total or 0


async def find_by_id(s: AsyncSession, patient_id: str) -> tuple[User, PatientProfile | None] | None:
    q = (
        select(User, PatientProfile)
        .outerjoin(PatientProfile, PatientProfile.user_id == User.id)
        .where(User.id == patient_id, User.role == "patient")
        .execution_options(populate_existing=True)
    )
    r = (await s.execute(q)).first()
    return (r[0], r[1]) if r else None
