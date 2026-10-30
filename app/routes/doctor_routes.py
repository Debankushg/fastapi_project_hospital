from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from app.controllers import consultation_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_doctor
from app.schemas.common_schema import Uuid
from app.schemas.consultation_schema import DoctorPatientsQuery

router = APIRouter(prefix="/doctor", tags=["Doctor"], dependencies=[Authed, Depends(require_doctor)])


# Patients assigned to the signed-in doctor.
@router.get("/patients")
async def list_patients(q: Annotated[DoctorPatientsQuery, Query()], user: CurrentUser, s: Session):
    return await consultation_controller.list_patients(s, user, q)


@router.get("/appointments/{id}")
async def detail(id: Uuid, user: CurrentUser, s: Session):
    return await consultation_controller.detail(s, user, id)


@router.post(
    "/appointments/{id}/prescriptions",
    summary="Upload a prescription",
    description="Send the PDF as the raw request body (Content-Type: application/pdf, max 5 MB). "
    "The original name goes in the X-File-Name header (URL-encoded).",
    openapi_extra={"requestBody": {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def add_prescription(
    id: Uuid,
    request: Request,
    user: CurrentUser,
    s: Session,
    x_file_name: Annotated[str | None, Header()] = None,
):
    return await consultation_controller.add_prescription(s, user, id, request, x_file_name)


@router.patch("/appointments/{id}/check")
async def check(id: Uuid, user: CurrentUser, s: Session):
    return await consultation_controller.check(s, user, id)
