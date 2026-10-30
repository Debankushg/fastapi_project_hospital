from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers import appointment_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_patient_or_reception, require_reception, require_role
from app.schemas.appointment_schema import (
    AppointmentListQuery,
    ApproveAppointmentIn,
    AvailabilityQuery,
    CreateAppointmentIn,
    RejectAppointmentIn,
)
from app.schemas.common_schema import Uuid

router = APIRouter(prefix="/appointments", tags=["Appointments"], dependencies=[Authed])
reception = [Depends(require_reception)]


# Patients (for themselves) and reception staff (on behalf of a patient) create requests.
@router.post("", dependencies=[Depends(require_patient_or_reception)])
async def create(body: CreateAppointmentIn, user: CurrentUser, s: Session):
    return await appointment_controller.create(s, user, body)


@router.get("/mine", dependencies=[Depends(require_role("patient"))])
async def mine(user: CurrentUser, s: Session):
    return await appointment_controller.mine(s, user)


# Reception queue.
@router.get("", dependencies=reception)
async def list_appointments(q: Annotated[AppointmentListQuery, Query()], s: Session):
    return await appointment_controller.list_appointments(s, q)


@router.get("/availability", dependencies=reception)
async def availability(q: Annotated[AvailabilityQuery, Query()], s: Session):
    return await appointment_controller.availability(s, q)


@router.patch("/{id}/approve", dependencies=reception)
async def approve(id: Uuid, body: ApproveAppointmentIn, user: CurrentUser, s: Session):
    return await appointment_controller.approve(s, user, id, body)


@router.patch("/{id}/reject", dependencies=reception)
async def reject(id: Uuid, body: RejectAppointmentIn, user: CurrentUser, s: Session):
    return await appointment_controller.reject(s, user, id, body)


# Patient cancels own; reception cancels any (checked in the service).
@router.patch("/{id}/cancel")
async def cancel(id: Uuid, user: CurrentUser, s: Session):
    return await appointment_controller.cancel(s, user, id)
