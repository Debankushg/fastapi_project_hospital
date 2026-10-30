from typing import Annotated

from fastapi import APIRouter, Query

from app.controllers import attendance_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireAdmin
from app.schemas.attendance_schema import AttendanceQuery, MarkAttendanceIn

router = APIRouter(prefix="/attendance", tags=["Attendance"], dependencies=[Authed, RequireAdmin])


@router.get("")
async def sheet(q: Annotated[AttendanceQuery, Query()], user: CurrentUser, s: Session):
    return await attendance_controller.sheet(s, user, q)


@router.post("")
async def mark(body: MarkAttendanceIn, user: CurrentUser, s: Session):
    return await attendance_controller.mark(s, user, body)
