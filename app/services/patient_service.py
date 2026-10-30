from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    appointment_repository,
    patient_profile_repository,
    patient_repository,
    prescription_repository,
    user_repository,
)
from app.schemas.patient_schema import PatientListQuery, UpdatePatientIn
from app.utils.file_storage_util import delete_prescription_files
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import to_patient_view
from app.utils.pagination_util import offset_of, to_page


async def list_patients(s: AsyncSession, q: PatientListQuery) -> dict:
    rows, total = await patient_repository.search(
        s,
        search=q.search,
        sort_by=q.sort_by,
        order=q.order,
        limit=q.page_size,
        offset=offset_of(q.page, q.page_size),
    )
    return to_page([to_patient_view(u, p) for u, p in rows], total, q.page, q.page_size)


async def get(s: AsyncSession, patient_id: str) -> dict:
    """Full patient details with their latest appointments."""
    found = await patient_repository.find_by_id(s, patient_id)
    if not found:
        raise HttpError(404, "Patient not found")
    rows, _ = await appointment_repository.list_appointments(s, patient_id=patient_id, limit=50, offset=0)
    return {"patient": to_patient_view(*found), "appointments": rows}


async def update(s: AsyncSession, patient_id: str, data: UpdatePatientIn) -> dict:
    """Edit a patient's details (all reception staff). Email and password are not editable here."""
    found = await patient_repository.find_by_id(s, patient_id)
    if not found:
        raise HttpError(404, "Patient not found")
    sent = data.model_dump(exclude_unset=True)

    account = {k: sent[k] for k in ("full_name", "phone") if k in sent}
    if account:
        user_repository.update(found[0], **account)
    profile = {k: v for k, v in sent.items() if k not in ("full_name", "phone")}
    if profile:
        await patient_profile_repository.upsert(s, patient_id, profile)
    await s.commit()
    return to_patient_view(*(await patient_repository.find_by_id(s, patient_id)))


async def remove(s: AsyncSession, patient_id: str) -> None:
    """Permanently deletes the patient with their profile and appointments (reception admin / super admin)."""
    found = await patient_repository.find_by_id(s, patient_id)
    if not found:
        raise HttpError(404, "Patient not found")
    files = await prescription_repository.stored_names_for_patient(s, patient_id)
    await user_repository.delete(s, found[0])
    await s.commit()
    await delete_prescription_files(files)
