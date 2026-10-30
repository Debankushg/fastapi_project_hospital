from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DutySchedule, User
from app.repositories import duty_schedule_repository
from app.schemas.duty_schema import DutyScheduleIn
from app.services import permission_service


def to_duty_view(d: DutySchedule) -> dict:
    return {
        "userId": d.user_id,
        "startTime": d.start_time.strftime("%H:%M"),
        "endTime": d.end_time.strftime("%H:%M"),
        "workDays": sorted(d.work_days),
        "updatedAt": d.updated_at,
    }


async def get_duty(s: AsyncSession, actor: User, user_id: str) -> dict | None:
    await permission_service.assert_can_manage_staff(s, actor, user_id)
    duty = await duty_schedule_repository.find_by_user(s, user_id)
    return to_duty_view(duty) if duty else None


async def set_duty(s: AsyncSession, actor: User, user_id: str, data: DutyScheduleIn) -> dict:
    await permission_service.assert_can_manage_staff(s, actor, user_id)
    saved = await duty_schedule_repository.upsert(
        s,
        user_id,
        start_time=data.start_time,
        end_time=data.end_time,
        work_days=data.work_days,
        updated_by=actor.id,
    )
    await s.commit()
    return to_duty_view(saved)
