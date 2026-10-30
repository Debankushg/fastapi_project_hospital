from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.user_schema import CreateUserIn, DoctorQuery, ListUsersQuery, SetActiveIn
from app.services import user_service
from app.utils.response_util import ok


async def create(s: AsyncSession, actor: User, body: CreateUserIn):
    return ok({"user": await user_service.create_user(s, actor, body)}, 201)


async def list_users(s: AsyncSession, actor: User, q: ListUsersQuery):
    return ok({"users": await user_service.list_users(s, actor, q.role)})


async def set_active(s: AsyncSession, actor: User, user_id: str, body: SetActiveIn):
    return ok({"user": await user_service.set_active(s, actor, user_id, body.is_active)})


async def remove(s: AsyncSession, actor: User, user_id: str):
    await user_service.delete_user(s, actor, user_id)
    return Response(status_code=204)


async def list_doctors(s: AsyncSession, q: DoctorQuery):
    return ok({"doctors": await user_service.list_doctors(s, q.specialty)})
