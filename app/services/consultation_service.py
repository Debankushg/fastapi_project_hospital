from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, User
from app.repositories import (
    appointment_repository,
    doctor_profile_repository,
    patient_repository,
    prescription_repository,
)
from app.schemas.consultation_schema import CheckedVisitsQuery, DoctorPatientsQuery
from app.services import permission_service
from app.utils.date_util import utc_now
from app.utils.file_storage_util import (
    delete_prescription_files,
    is_pdf,
    safe_file_name,
    save_prescription_file,
)
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import row, to_patient_view
from app.utils.pagination_util import offset_of, to_page

MAX_PRESCRIPTION_BYTES = 5 * 1024 * 1024
MAX_PRESCRIPTIONS_PER_VISIT = 5


async def _own_appointment(s: AsyncSession, actor: User, appointment_id: str) -> Appointment:
    """The doctor's own appointment, or 404 (we do not reveal other doctors' appointments)."""
    appt = await appointment_repository.find_by_id(s, appointment_id)
    if not appt or appt.doctor_id != actor.id or appt.status not in ("approved", "checked"):
        raise HttpError(404, "Appointment not found")
    return appt


def _with_prescriptions(rows: list[dict], rx: list[dict]) -> list[dict]:
    return [{**r, "prescriptions": [p for p in rx if p["appointmentId"] == r["id"]]} for r in rows]


async def list_patients(s: AsyncSession, actor: User, q: DoctorPatientsQuery) -> dict:
    """Patients assigned to this doctor (approved = still to see, checked = done)."""
    rows, total = await appointment_repository.list_appointments(
        s,
        doctor_id=actor.id,
        statuses=[q.status] if q.status else ["approved", "checked"],
        day=q.date,
        search=q.search,
        sort="date_asc",
        limit=q.page_size,
        offset=offset_of(q.page, q.page_size),
    )
    return to_page(rows, total, q.page, q.page_size)


async def detail(s: AsyncSession, actor: User, appointment_id: str) -> dict:
    """Full picture for one assigned patient: details, this visit's prescriptions and visit history."""
    appt = await _own_appointment(s, actor, appointment_id)
    patient = await patient_repository.find_by_id(s, appt.patient_id)
    if not patient:
        raise HttpError(404, "Patient not found")

    rows, _ = await appointment_repository.list_appointments(
        s, patient_id=appt.patient_id, statuses=["approved", "checked"], sort="date_desc", limit=50, offset=0
    )
    rx = await prescription_repository.list_by_appointment_ids(s, [r["id"] for r in rows])
    with_rx = _with_prescriptions(rows, rx)
    return {
        "appointment": next(r for r in with_rx if r["id"] == appointment_id),
        "patient": to_patient_view(*patient),
        "history": [r for r in with_rx if r["id"] != appointment_id],
    }


async def add_prescription(s: AsyncSession, actor: User, appointment_id: str, file: bytes, raw_name: str | None) -> dict:
    appt = await _own_appointment(s, actor, appointment_id)
    if not file:
        raise HttpError(415, "Send the PDF as the request body with Content-Type: application/pdf")
    if len(file) > MAX_PRESCRIPTION_BYTES:
        raise HttpError(413, "File too large (max 5 MB)")
    if not is_pdf(file):
        raise HttpError(400, "Only PDF files are allowed")
    existing = await prescription_repository.list_by_appointment_ids(s, [appointment_id])
    if len(existing) >= MAX_PRESCRIPTIONS_PER_VISIT:
        raise HttpError(409, f"At most {MAX_PRESCRIPTIONS_PER_VISIT} prescriptions per visit")

    stored_name = await save_prescription_file(file)
    rx = prescription_repository.create(
        s,
        appointment_id=appt.id,
        patient_id=appt.patient_id,
        doctor_id=actor.id,
        file_name=safe_file_name(raw_name),
        stored_name=stored_name,
        size_bytes=len(file),
    )
    await s.commit()
    await s.refresh(rx)
    public = row(rx)
    del public["storedName"], public["patientId"]
    return public


async def check(s: AsyncSession, actor: User, appointment_id: str) -> None:
    """Marks the patient as checked: the visit then shows up for reception and accounts."""
    appt = await _own_appointment(s, actor, appointment_id)
    if appt.status == "checked":
        raise HttpError(409, "Patient is already marked as checked")
    profile = await doctor_profile_repository.find_by_user(s, actor.id)
    appointment_repository.update(
        appt,
        status="checked",
        checked_at=utc_now(),
        checked_by=actor.id,
        checked_fee=profile.consultation_fee if profile else None,
    )
    await s.commit()


async def list_checked(s: AsyncSession, actor: User, q: CheckedVisitsQuery) -> dict:
    """Checked patients, newest first: shared with reception and accounts. Reception also gets the
    prescription metadata (to open the PDFs); accounts only sees how many are attached."""
    rows, total = await appointment_repository.list_appointments(
        s,
        status="checked",
        day=q.date,
        search=q.search,
        sort="checked_desc",
        limit=q.page_size,
        offset=offset_of(q.page, q.page_size),
    )
    can_open_files = await permission_service.can_use_reception(s, actor)
    rx = await prescription_repository.list_by_appointment_ids(s, [r["id"] for r in rows]) if can_open_files else []
    return to_page(_with_prescriptions(rows, rx), total, q.page, q.page_size)


async def remove_prescription(s: AsyncSession, actor: User, prescription_id: str) -> None:
    """Removes a prescription (the doctor who uploaded it)."""
    rx = await prescription_repository.find_by_id(s, prescription_id)
    if not rx or rx.doctor_id != actor.id:
        raise HttpError(404, "Prescription not found")
    stored_name = rx.stored_name
    await prescription_repository.delete(s, rx)
    await s.commit()
    await delete_prescription_files([stored_name])
