from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.admin_schema import CreateAdminIn, DemoteAdminIn, UpdateAdminWorkIn
from app.services import admin_service
from app.utils.response_util import ok


async def list_admins(s: AsyncSession):
    return ok({"admins": await admin_service.list_admins(s)})


async def create(s: AsyncSession, actor: User, body: CreateAdminIn):
    return ok(await admin_service.create_admin(s, actor, body), 201)


async def promote(s: AsyncSession, actor: User, user_id: str, body: UpdateAdminWorkIn):
    return ok(await admin_service.promote(s, actor, user_id, body))


async def replace_assignments(s: AsyncSession, actor: User, user_id: str, body: UpdateAdminWorkIn):
    return ok(await admin_service.replace_assignments(s, actor, user_id, body))


async def get_assignments(s: AsyncSession, user_id: str):
    return ok({"assignments": await admin_service.get_assignments(s, user_id)})


async def demote(s: AsyncSession, user_id: str, body: DemoteAdminIn):
    return ok({"user": await admin_service.demote(s, user_id, body.role)})
