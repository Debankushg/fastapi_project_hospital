from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers import analytics_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_checked_visits_access, require_doctor_insights
from app.schemas.analytics_schema import AnalyticsQuery, AttendanceCalendarQuery

router = APIRouter(prefix="/analytics", tags=["Analytics"], dependencies=[Authed])


# Patient volume: aggregate counts, every signed-in user.
@router.get("/patients")
async def patients(q: Annotated[AnalyticsQuery, Query()], s: Session):
    return await analytics_controller.patients(s, q)


# Revenue (consultation fees of checked visits): reception, accounts, super admin.
@router.get("/revenue", dependencies=[Depends(require_checked_visits_access)])
async def revenue(q: Annotated[AnalyticsQuery, Query()], s: Session):
    return await analytics_controller.revenue(s, q)


# Checked vs unchecked per doctor: doctors and super admin.
@router.get("/doctors", dependencies=[Depends(require_doctor_insights)])
async def doctors(q: Annotated[AnalyticsQuery, Query()], s: Session):
    return await analytics_controller.doctors(s, q)


# Attendance calendar: staff see their own; managers pass ?userId= for staff they manage.
@router.get("/attendance-calendar")
async def attendance_calendar(q: Annotated[AttendanceCalendarQuery, Query()], user: CurrentUser, s: Session):
    return await analytics_controller.attendance_calendar(s, user, q)
