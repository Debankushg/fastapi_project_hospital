from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LeaveRecord, User


def create(s: AsyncSession, **values) -> LeaveRecord:
    leave = LeaveRecord(**values)
    s.add(leave)
    return leave


async def find_by_id(s: AsyncSession, leave_id: str) -> LeaveRecord | None:
    return await s.get(LeaveRecord, leave_id)


async def delete(s: AsyncSession, leave: LeaveRecord) -> None:
    await s.delete(leave)


async def list_leaves(
    s: AsyncSession,
    user_ids: list[str],
    status: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Leaves overlapping the optional [start, end] window, joined with the staff member's name and role."""
    if not user_ids:
        return []
    q = select(LeaveRecord, User.full_name, User.role).join(User, User.id == LeaveRecord.user_id)
    q = q.where(LeaveRecord.user_id.in_(user_ids))
    if status:
        q = q.where(LeaveRecord.status == status)
    if start:
        q = q.where(LeaveRecord.end_date >= start)
    if end:
        q = q.where(LeaveRecord.start_date <= end)
    q = q.order_by(LeaveRecord.start_date.desc())
    return [
        {
            "id": lv.id,
            "userId": lv.user_id,
            "userName": name,
            "userRole": role,
            "leaveType": lv.leave_type,
            "startDate": lv.start_date,
            "endDate": lv.end_date,
            "reason": lv.reason,
            "status": lv.status,
            "reviewNote": lv.review_note,
            "reviewedAt": lv.reviewed_at,
            "createdAt": lv.created_at,
        }
        for lv, name, role in (await s.execute(q)).all()
    ]


async def user_ids_on_leave(s: AsyncSession, user_ids: list[str], day: date) -> set[str]:
    """Users with an approved leave covering `day`."""
    if not user_ids:
        return set()
    q = select(LeaveRecord.user_id).where(
        LeaveRecord.user_id.in_(user_ids),
        LeaveRecord.status == "approved",
        LeaveRecord.end_date >= day,
        LeaveRecord.start_date <= day,
    )
    return set((await s.scalars(q)).all())
