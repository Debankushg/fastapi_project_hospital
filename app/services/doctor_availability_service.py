from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    appointment_repository,
    attendance_repository,
    doctor_profile_repository,
    duty_schedule_repository,
    leave_repository,
)
from app.services.duty_service import to_duty_view
from app.utils.date_util import weekday_of


async def for_date(s: AsyncSession, specialty: str, day: date) -> list[dict]:
    """Active doctors of a specialty with their availability on a date.
    Unavailable when: marked absent / on leave in attendance, covered by approved leave,
    or the date is not one of their duty days. Doctors without a duty schedule count as available."""
    doctors = await doctor_profile_repository.list_active(s, specialty)
    ids = [d["id"] for d in doctors]
    if not ids:
        return []

    schedules = {d.user_id: d for d in await duty_schedule_repository.list_by_user_ids(s, ids)}
    status_by = {r.user_id: r.status for r in await attendance_repository.list_by_date(s, day, ids)}
    on_leave = await leave_repository.user_ids_on_leave(s, ids, day)
    workload = await appointment_repository.count_approved_by_doctors(s, ids, day)

    result = []
    for d in doctors:
        schedule = schedules.get(d["id"])
        status = status_by.get(d["id"])
        reason = None
        if status == "absent":
            reason = "absent"
        elif status == "on_leave" or d["id"] in on_leave:
            reason = "on_leave"
        elif schedule and weekday_of(day) not in schedule.work_days:
            reason = "not_on_duty"
        result.append(
            {
                **d,
                "duty": to_duty_view(schedule) if schedule else None,
                "appointmentsThatDay": workload.get(d["id"], 0),
                "available": reason is None,
                "reason": reason,
            }
        )
    return result
