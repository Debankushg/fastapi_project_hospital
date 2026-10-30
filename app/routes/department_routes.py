from fastapi import APIRouter

from app.controllers import department_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireAdmin

router = APIRouter(prefix="/department", tags=["Department"], dependencies=[Authed, RequireAdmin])


@router.get("/overview")
async def overview(user: CurrentUser, s: Session):
    return await department_controller.overview(s, user)


@router.get("/staff")
async def staff(user: CurrentUser, s: Session):
    return await department_controller.staff(s, user)
