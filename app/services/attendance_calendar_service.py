from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import attendance_repository, duty_schedule_repository, leave_repository
from app.schemas.analytics_schema import AttendanceCalendarQuery
from app.services import permission_service
from app.services.duty_service import to_duty_view
from app.utils.date_util import each_date, last_day_of, utc_now, weekday_of
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import to_public_user

STAFF_ROLES = ["admin", "doctor", "receptionist", "pathologist", "accounts"]


async def month(s: AsyncSession, actor: User, q: AttendanceCalendarQuery) -> dict:
    """One month of a staff member's attendance: per day the status, note, approved leave and whether it is a
    duty day, plus a summary. Staff see their own; managers may pass `userId` for staff they manage."""
    if q.user_id and q.user_id != actor.id:
        target = await permission_service.assert_can_manage_staff(s, actor, q.user_id)
    else:
        if actor.role not in STAFF_ROLES:
            raise HttpError(400, "Attendance is tracked for staff only. Choose a staff member to view.")
        target = actor

    start = date.fromisoformat(f"{q.month}-01")
    end = last_day_of(q.month)
    records = await attendance_repository.list_by_user(s, target.id, start, end)
    leaves = await leave_repository.list_leaves(s, [target.id], status="approved", start=start, end=end)
    duty = await duty_schedule_repository.find_by_user(s, target.id)

    by_date = {r.date: r for r in records}
    leave_by_date: dict[date, str] = {}
    for lv in leaves:
        for d in each_date(lv["startDate"], lv["endDate"]):
            leave_by_date[d] = lv["leaveType"]

    today = q.today or utc_now().date()
    duty_view = to_duty_view(duty) if duty else None

    days = []
    for d in each_date(start, end):
        rec = by_date.get(d)
        days.append(
            {
                "date": d,
                "weekday": weekday_of(d),
                "status": rec.status if rec else None,
                "notes": rec.notes if rec else None,
                "leaveType": leave_by_date.get(d),
                "isWorkDay": weekday_of(d) in duty_view["workDays"] if duty_view else None,
            }
        )

    def count(status: str) -> int:
        return sum(1 for d in days if d["status"] == status)

    unmarked = (
        sum(1 for d in days if d["date"] <= today and d["isWorkDay"] and not d["status"] and not d["leaveType"])
        if duty_view
        else None
    )
    return {
        "month": q.month,
        "user": to_public_user(target),
        "duty": duty_view,
        "days": days,
        "summary": {
            "present": count("present"),
            "late": count("late"),
            "halfDay": count("half_day"),
            "absent": count("absent"),
            "onLeave": sum(1 for d in days if d["status"] == "on_leave" or (not d["status"] and d["leaveType"])),
            "unmarked": unmarked,
        },
    }
