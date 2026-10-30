from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers import patient_controller
from app.db import Session
from app.middleware.auth_middleware import Authed
from app.middleware.rbac_middleware import require_reception, require_reception_admin
from app.schemas.common_schema import Uuid
from app.schemas.patient_schema import PatientListQuery, UpdatePatientIn

router = APIRouter(prefix="/patients", tags=["Patients"], dependencies=[Authed])
reception = [Depends(require_reception)]


# Reception staff: view and edit patients.
@router.get("", dependencies=reception)
async def list_patients(q: Annotated[PatientListQuery, Query()], s: Session):
    return await patient_controller.list_patients(s, q)


@router.get("/{id}", dependencies=reception)
async def get_patient(id: Uuid, s: Session):
    return await patient_controller.get(s, id)


@router.patch("/{id}", dependencies=reception)
async def update_patient(id: Uuid, body: UpdatePatientIn, s: Session):
    return await patient_controller.update(s, id, body)


# Only the admin of the reception department (or the super admin) may delete a patient.
@router.delete("/{id}", status_code=204, dependencies=[Depends(require_reception_admin)])
async def remove_patient(id: Uuid, s: Session):
    return await patient_controller.remove(s, id)
