from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import attendance_repository
from app.schemas.attendance_schema import MarkAttendanceIn
from app.services import department_service, permission_service
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import row, to_public_user


def _latest_allowed_date() -> date:
    """Latest date any timezone could currently be on (UTC+14), so "today" is never rejected."""
    return (datetime.now(timezone.utc) + timedelta(hours=14)).date()


async def mark(s: AsyncSession, actor: User, data: MarkAttendanceIn) -> dict:
    await permission_service.assert_can_manage_staff(s, actor, data.user_id)
    if data.date > _latest_allowed_date():
        raise HttpError(400, "Cannot mark attendance for a future date")
    record = await attendance_repository.upsert(
        s, user_id=data.user_id, date=data.date, status=data.status, notes=data.notes, marked_by=actor.id
    )
    await s.commit()
    return row(record)


async def sheet(s: AsyncSession, actor: User, day: date) -> list[dict]:
    """Daily sheet: every managed staff member with their record for the date (or null)."""
    staff = await department_service.list_staff(s, actor)
    records = await attendance_repository.list_by_date(s, day, [m.id for m in staff])
    by_user = {r.user_id: r for r in records}
    return [
        {
            "user": to_public_user(m),
            "attendance": {"status": by_user[m.id].status, "notes": by_user[m.id].notes} if m.id in by_user else None,
        }
        for m in staff
    ]
