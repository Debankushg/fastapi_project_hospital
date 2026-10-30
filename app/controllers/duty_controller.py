from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.duty_schema import DutyScheduleIn
from app.services import duty_service
from app.utils.response_util import ok


async def get(s: AsyncSession, actor: User, user_id: str):
    return ok({"duty": await duty_service.get_duty(s, actor, user_id)})


async def set_duty(s: AsyncSession, actor: User, user_id: str, body: DutyScheduleIn):
    return ok({"duty": await duty_service.set_duty(s, actor, user_id, body)})
