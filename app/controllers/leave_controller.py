from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.leave_schema import CreateLeaveIn, LeaveQuery, RequestLeaveIn, ReviewLeaveIn
from app.services import leave_service
from app.utils.response_util import ok


async def record(s: AsyncSession, actor: User, body: CreateLeaveIn):
    return ok({"leave": await leave_service.record(s, actor, body)}, 201)


async def request(s: AsyncSession, actor: User, body: RequestLeaveIn):
    return ok({"leave": await leave_service.request(s, actor, body)}, 201)


async def review(s: AsyncSession, actor: User, leave_id: str, body: ReviewLeaveIn):
    return ok({"leave": await leave_service.review(s, actor, leave_id, body)})


async def mine(s: AsyncSession, actor: User):
    return ok({"leaves": await leave_service.mine(s, actor)})


async def list_leaves(s: AsyncSession, actor: User, q: LeaveQuery):
    return ok({"leaves": await leave_service.list_leaves(s, actor, q)})


async def remove(s: AsyncSession, actor: User, leave_id: str):
    await leave_service.remove(s, actor, leave_id)
    return Response(status_code=204)
