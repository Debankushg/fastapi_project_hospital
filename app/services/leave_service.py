from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LeaveRecord, User
from app.repositories import attendance_repository, leave_repository
from app.schemas.leave_schema import CreateLeaveIn, LeaveQuery, RequestLeaveIn, ReviewLeaveIn
from app.services import department_service, permission_service
from app.utils.date_util import each_date, utc_now
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import row


async def _apply_to_attendance(s: AsyncSession, leave: LeaveRecord, marked_by: str) -> None:
    """Approved leave shows up as "on leave" in the attendance sheet for every day of the leave."""
    await attendance_repository.mark_dates(
        s, leave.user_id, each_date(leave.start_date, leave.end_date), "on_leave", marked_by
    )


async def record(s: AsyncSession, actor: User, data: CreateLeaveIn) -> dict:
    """Admin records leave for a staff member: approved immediately."""
    await permission_service.assert_can_manage_staff(s, actor, data.user_id)
    leave = leave_repository.create(
        s,
        user_id=data.user_id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status="approved",
        reviewed_by=actor.id,
        reviewed_at=utc_now(),
        recorded_by=actor.id,
    )
    await _apply_to_attendance(s, leave, actor.id)
    await s.commit()
    await s.refresh(leave)
    return row(leave)


async def request(s: AsyncSession, actor: User, data: RequestLeaveIn) -> dict:
    """Staff member asks for leave; an admin of their department reviews it."""
    if actor.role in ("patient", "super_admin"):
        raise HttpError(403, "Only staff members can request leave")
    leave = leave_repository.create(
        s,
        user_id=actor.id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status="pending",
        recorded_by=actor.id,
    )
    await s.commit()
    await s.refresh(leave)
    return row(leave)


async def review(s: AsyncSession, actor: User, leave_id: str, data: ReviewLeaveIn) -> dict:
    leave = await leave_repository.find_by_id(s, leave_id)
    if not leave:
        raise HttpError(404, "Leave record not found")
    await permission_service.assert_can_manage_staff(s, actor, leave.user_id)
    if leave.status != "pending":
        raise HttpError(409, f"Leave was already {leave.status}")

    leave.status = data.status
    leave.review_note = data.note
    leave.reviewed_by = actor.id
    leave.reviewed_at = utc_now()
    if data.status == "approved":
        await _apply_to_attendance(s, leave, actor.id)
    await s.commit()
    return row(leave)


async def mine(s: AsyncSession, actor: User) -> list[dict]:
    return await leave_repository.list_leaves(s, [actor.id])


async def list_leaves(s: AsyncSession, actor: User, q: LeaveQuery) -> list[dict]:
    if q.user_id:
        await permission_service.assert_can_manage_staff(s, actor, q.user_id)
        user_ids = [q.user_id]
    else:
        user_ids = [m.id for m in await department_service.list_staff(s, actor)]
    return await leave_repository.list_leaves(s, user_ids, q.status, q.from_, q.to)


async def remove(s: AsyncSession, actor: User, leave_id: str) -> None:
    """Staff may cancel their own pending request; admins may delete leave of staff they manage."""
    leave = await leave_repository.find_by_id(s, leave_id)
    if not leave:
        raise HttpError(404, "Leave record not found")
    if leave.user_id == actor.id:
        if leave.status != "pending":
            raise HttpError(403, "Only pending requests can be cancelled")
    else:
        await permission_service.assert_can_manage_staff(s, actor, leave.user_id)
    await leave_repository.delete(s, leave)
    await s.commit()
