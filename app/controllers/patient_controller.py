from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.patient_schema import PatientListQuery, UpdatePatientIn
from app.services import patient_service
from app.utils.response_util import ok


async def list_patients(s: AsyncSession, q: PatientListQuery):
    return ok(await patient_service.list_patients(s, q))


async def get(s: AsyncSession, patient_id: str):
    return ok(await patient_service.get(s, patient_id))


async def update(s: AsyncSession, patient_id: str, body: UpdatePatientIn):
    return ok({"patient": await patient_service.update(s, patient_id, body)})


async def remove(s: AsyncSession, patient_id: str):
    await patient_service.remove(s, patient_id)
    return Response(status_code=204)
