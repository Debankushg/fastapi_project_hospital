from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.attendance_schema import AttendanceQuery, MarkAttendanceIn
from app.services import attendance_service
from app.utils.response_util import ok


async def mark(s: AsyncSession, actor: User, body: MarkAttendanceIn):
    return ok({"attendance": await attendance_service.mark(s, actor, body)}, 201)


async def sheet(s: AsyncSession, actor: User, q: AttendanceQuery):
    return ok({"date": q.date, "entries": await attendance_service.sheet(s, actor, q.date)})
