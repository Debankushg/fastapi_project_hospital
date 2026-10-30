from fastapi import APIRouter, Depends

from app.controllers import consultation_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_doctor
from app.schemas.common_schema import Uuid

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"], dependencies=[Authed])


# Access is decided in the service (patient, treating doctors, reception, super admin).
@router.get("/{id}/file")
async def prescription_file(id: Uuid, user: CurrentUser, s: Session):
    return await consultation_controller.prescription_file(s, user, id)


@router.delete("/{id}", status_code=204, dependencies=[Depends(require_doctor)])
async def remove_prescription(id: Uuid, user: CurrentUser, s: Session):
    return await consultation_controller.remove_prescription(s, user, id)
