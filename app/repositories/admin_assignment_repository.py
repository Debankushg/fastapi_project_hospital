from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAssignment, User


async def list_all(s: AsyncSession) -> list[AdminAssignment]:
    return list((await s.scalars(select(AdminAssignment))).all())


async def list_by_admin(s: AsyncSession, admin_id: str) -> list[AdminAssignment]:
    return list((await s.scalars(select(AdminAssignment).where(AdminAssignment.admin_id == admin_id))).all())


async def has_area(s: AsyncSession, admin_id: str, area: str) -> bool:
    q = select(AdminAssignment.id).where(AdminAssignment.admin_id == admin_id, AdminAssignment.area == area)
    return (await s.scalar(q)) is not None


async def replace_for_admin(s: AsyncSession, admin_id: str, assigned_by: str, items: list[dict]) -> list[dict]:
    """Replaces the whole set of work areas for an admin. Every department has exactly one admin, so any
    area in `items` that another admin holds is taken away from them. Returns who lost what.
    `items` are {"area", "notes"} dicts. Flush only; the service commits (use one transaction)."""
    areas = [a["area"] for a in items]
    taken = and_(AdminAssignment.area.in_(areas), AdminAssignment.admin_id != admin_id)
    rows = (
        await s.execute(
            select(AdminAssignment.area, AdminAssignment.admin_id, User.full_name)
            .join(User, User.id == AdminAssignment.admin_id)
            .where(taken)
        )
    ).all()
    displaced = [{"area": r.area, "fromAdminId": r.admin_id, "fromAdminName": r.full_name} for r in rows]
    if displaced:
        await s.execute(delete(AdminAssignment).where(taken))
    await s.execute(delete(AdminAssignment).where(AdminAssignment.admin_id == admin_id))
    s.add_all(AdminAssignment(admin_id=admin_id, assigned_by=assigned_by, area=a["area"], notes=a.get("notes")) for a in items)
    await s.flush()
    return displaced


async def delete_by_admin(s: AsyncSession, admin_id: str) -> None:
    await s.execute(delete(AdminAssignment).where(AdminAssignment.admin_id == admin_id))
