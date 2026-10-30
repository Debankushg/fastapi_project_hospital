from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.appointment_schema import (
    AppointmentListQuery,
    ApproveAppointmentIn,
    AvailabilityQuery,
    CreateAppointmentIn,
    RejectAppointmentIn,
)
from app.services import appointment_service
from app.utils.response_util import ok


async def create(s: AsyncSession, actor: User, body: CreateAppointmentIn):
    return ok({"appointment": await appointment_service.create(s, actor, body)}, 201)


async def mine(s: AsyncSession, actor: User):
    return ok({"appointments": await appointment_service.mine(s, actor)})


async def list_appointments(s: AsyncSession, q: AppointmentListQuery):
    return ok(await appointment_service.list_all(s, q))


async def availability(s: AsyncSession, q: AvailabilityQuery):
    return ok({"doctors": await appointment_service.availability(s, q)})


async def approve(s: AsyncSession, actor: User, appointment_id: str, body: ApproveAppointmentIn):
    return ok({"appointment": await appointment_service.approve(s, actor, appointment_id, body)})


async def reject(s: AsyncSession, actor: User, appointment_id: str, body: RejectAppointmentIn):
    return ok({"appointment": await appointment_service.reject(s, actor, appointment_id, body.note)})


async def cancel(s: AsyncSession, actor: User, appointment_id: str):
    return ok({"appointment": await appointment_service.cancel(s, actor, appointment_id)})
