from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.analytics_schema import AnalyticsQuery, AttendanceCalendarQuery
from app.services import analytics_service, attendance_calendar_service
from app.utils.response_util import ok


async def patients(s: AsyncSession, q: AnalyticsQuery):
    return ok(await analytics_service.patients(s, q))


async def revenue(s: AsyncSession, q: AnalyticsQuery):
    return ok(await analytics_service.revenue(s, q))


async def doctors(s: AsyncSession, q: AnalyticsQuery):
    return ok(await analytics_service.doctors(s, q))


async def attendance_calendar(s: AsyncSession, actor: User, q: AttendanceCalendarQuery):
    return ok(await attendance_calendar_service.month(s, actor, q))
