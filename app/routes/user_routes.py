from typing import Annotated

from fastapi import APIRouter, Query

from app.controllers import user_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireAdmin, RequireSuperAdmin
from app.schemas.common_schema import Uuid
from app.schemas.user_schema import CreateUserIn, DoctorQuery, ListUsersQuery, SetActiveIn

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Authed])


# Directory of doctors, readable by any signed-in user (e.g. patients picking a specialist).
@router.get("/doctors")
async def list_doctors(q: Annotated[DoctorQuery, Query()], s: Session):
    return await user_controller.list_doctors(s, q)


# Management endpoints: super admin, or admin within assigned areas (enforced in the service).
@router.post("", dependencies=[RequireAdmin])
async def create(body: CreateUserIn, user: CurrentUser, s: Session):
    return await user_controller.create(s, user, body)


@router.get("", dependencies=[RequireAdmin])
async def list_users(q: Annotated[ListUsersQuery, Query()], user: CurrentUser, s: Session):
    return await user_controller.list_users(s, user, q)


@router.patch("/{id}/active", dependencies=[RequireAdmin])
async def set_active(id: Uuid, body: SetActiveIn, user: CurrentUser, s: Session):
    return await user_controller.set_active(s, user, id, body)


# Permanent delete (any non-super-admin user, including admins): super admin only.
@router.delete("/{id}", status_code=204, dependencies=[RequireSuperAdmin])
async def remove(id: Uuid, user: CurrentUser, s: Session):
    return await user_controller.remove(s, user, id)
