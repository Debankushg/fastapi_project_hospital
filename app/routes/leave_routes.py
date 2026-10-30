from typing import Annotated

from fastapi import APIRouter, Query

from app.controllers import leave_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import RequireAdmin
from app.schemas.common_schema import Uuid
from app.schemas.leave_schema import CreateLeaveIn, LeaveQuery, RequestLeaveIn, ReviewLeaveIn

router = APIRouter(prefix="/leaves", tags=["Leaves"], dependencies=[Authed])


# Any staff member: request leave and see their own requests.
@router.post("/request")
async def request_leave(body: RequestLeaveIn, user: CurrentUser, s: Session):
    return await leave_controller.request(s, user, body)


@router.get("/mine")
async def mine(user: CurrentUser, s: Session):
    return await leave_controller.mine(s, user)


# Admins (within their areas) and super admin: list, record, approve/reject.
@router.get("", dependencies=[RequireAdmin])
async def list_leaves(q: Annotated[LeaveQuery, Query()], user: CurrentUser, s: Session):
    return await leave_controller.list_leaves(s, user, q)


@router.post("", dependencies=[RequireAdmin])
async def record(body: CreateLeaveIn, user: CurrentUser, s: Session):
    return await leave_controller.record(s, user, body)


@router.patch("/{id}/review", dependencies=[RequireAdmin])
async def review(id: Uuid, body: ReviewLeaveIn, user: CurrentUser, s: Session):
    return await leave_controller.review(s, user, id, body)


# Staff cancel their own pending request; admins delete (permission checked in the service).
@router.delete("/{id}", status_code=204)
async def remove(id: Uuid, user: CurrentUser, s: Session):
    return await leave_controller.remove(s, user, id)
