from fastapi import APIRouter

from app.controllers import admin_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireSuperAdmin
from app.schemas.admin_schema import CreateAdminIn, DemoteAdminIn, UpdateAdminWorkIn
from app.schemas.common_schema import Uuid

router = APIRouter(prefix="/admins", tags=["Admins"], dependencies=[Authed, RequireSuperAdmin])


@router.get("")
async def list_admins(s: Session):
    return await admin_controller.list_admins(s)


@router.post("")
async def create(body: CreateAdminIn, user: CurrentUser, s: Session):
    return await admin_controller.create(s, user, body)


@router.post("/{user_id}/promote")
async def promote(user_id: Uuid, body: UpdateAdminWorkIn, user: CurrentUser, s: Session):
    return await admin_controller.promote(s, user, user_id, body)


@router.post("/{user_id}/demote")
async def demote(user_id: Uuid, body: DemoteAdminIn, s: Session):
    return await admin_controller.demote(s, user_id, body)


@router.get("/{user_id}/assignments")
async def get_assignments(user_id: Uuid, s: Session):
    return await admin_controller.get_assignments(s, user_id)


@router.put("/{user_id}/assignments")
async def replace_assignments(user_id: Uuid, body: UpdateAdminWorkIn, user: CurrentUser, s: Session):
    return await admin_controller.replace_assignments(s, user, user_id, body)
