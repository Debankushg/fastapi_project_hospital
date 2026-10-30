from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Prescription


def create(s: AsyncSession, **values) -> Prescription:
    rx = Prescription(**values)
    s.add(rx)
    return rx


async def find_by_id(s: AsyncSession, prescription_id: str) -> Prescription | None:
    return await s.get(Prescription, prescription_id)


async def delete(s: AsyncSession, rx: Prescription) -> None:
    await s.delete(rx)


async def list_by_appointment_ids(s: AsyncSession, ids: list[str]) -> list[dict]:
    """Metadata safe to return to clients (never the stored file name)."""
    if not ids:
        return []
    q = select(Prescription).where(Prescription.appointment_id.in_(ids)).order_by(Prescription.created_at)
    return [
        {
            "id": p.id,
            "appointmentId": p.appointment_id,
            "doctorId": p.doctor_id,
            "fileName": p.file_name,
            "sizeBytes": p.size_bytes,
            "createdAt": p.created_at,
        }
        for p in (await s.scalars(q)).all()
    ]


async def stored_names_for_patient(s: AsyncSession, patient_id: str) -> list[str]:
    """Stored file names of a patient's prescriptions, to clean up the disk when the patient is deleted
    (their rows cascade). A deleted doctor's prescriptions are kept: they belong to the patient."""
    return list((await s.scalars(select(Prescription.stored_name).where(Prescription.patient_id == patient_id))).all())
