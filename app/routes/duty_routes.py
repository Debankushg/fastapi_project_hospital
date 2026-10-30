from fastapi import APIRouter

from app.controllers import duty_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireAdmin
from app.schemas.common_schema import Uuid
from app.schemas.duty_schema import DutyScheduleIn

router = APIRouter(prefix="/staff", tags=["Duty"], dependencies=[Authed, RequireAdmin])


@router.get("/{user_id}/duty")
async def get_duty(user_id: Uuid, user: CurrentUser, s: Session):
    return await duty_controller.get(s, user, user_id)


@router.put("/{user_id}/duty")
async def set_duty(user_id: Uuid, body: DutyScheduleIn, user: CurrentUser, s: Session):
    return await duty_controller.set_duty(s, user, user_id, body)
