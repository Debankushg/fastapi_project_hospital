from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, User
from app.repositories import appointment_repository, patient_repository, prescription_repository
from app.schemas.appointment_schema import (
    AppointmentListQuery,
    ApproveAppointmentIn,
    AvailabilityQuery,
    CreateAppointmentIn,
)
from app.services import doctor_availability_service, permission_service
from app.utils.date_util import utc_now
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import row
from app.utils.pagination_util import offset_of, to_page


def _earliest_allowed_date() -> date:
    """Earliest date any timezone could currently be on (UTC-12), so "today" is never rejected."""
    return (datetime.now(timezone.utc) - timedelta(hours=12)).date()


async def _load_or_fail(s: AsyncSession, appointment_id: str) -> Appointment:
    appt = await appointment_repository.find_by_id(s, appointment_id)
    if not appt:
        raise HttpError(404, "Appointment not found")
    return appt


async def create(s: AsyncSession, actor: User, data: CreateAppointmentIn) -> dict:
    """Patients book for themselves; receptionists/super admin book on behalf of a patient."""
    patient_id = actor.id
    if actor.role != "patient":
        if not data.patient_id:
            raise HttpError(400, "patientId is required")
        if not await patient_repository.find_by_id(s, data.patient_id):
            raise HttpError(404, "Patient not found")
        patient_id = data.patient_id
    if data.date < _earliest_allowed_date():
        raise HttpError(400, "The appointment date cannot be in the past")

    if data.preferred_doctor_id:
        doctors = await doctor_availability_service.for_date(s, data.specialty, data.date)
        if not any(d["id"] == data.preferred_doctor_id for d in doctors):
            raise HttpError(400, "Preferred doctor does not match the required specialty")

    appt = appointment_repository.create(
        s,
        patient_id=patient_id,
        specialty=data.specialty,
        requested_doctor_id=data.preferred_doctor_id,
        appointment_date=data.date,
        reason=data.reason,
        created_by=actor.id,
    )
    await s.commit()
    await s.refresh(appt)
    return row(appt)


async def mine(s: AsyncSession, actor: User) -> list[dict]:
    """The patient's own appointments, each with its prescriptions (PDF metadata)."""
    rows, _ = await appointment_repository.list_appointments(s, patient_id=actor.id, limit=100, offset=0)
    rx = await prescription_repository.list_by_appointment_ids(s, [r["id"] for r in rows])
    return [{**r, "prescriptions": [p for p in rx if p["appointmentId"] == r["id"]]} for r in rows]


async def list_all(s: AsyncSession, q: AppointmentListQuery) -> dict:
    rows, total = await appointment_repository.list_appointments(
        s, status=q.status, day=q.date, search=q.search, limit=q.page_size, offset=offset_of(q.page, q.page_size)
    )
    return to_page(rows, total, q.page, q.page_size)


async def availability(s: AsyncSession, q: AvailabilityQuery) -> list[dict]:
    return await doctor_availability_service.for_date(s, q.specialty, q.date)


async def approve(s: AsyncSession, actor: User, appointment_id: str, data: ApproveAppointmentIn) -> dict:
    """Assign a doctor and approve. The doctor must match the patient's required specialty and be
    available that day. An already approved appointment can be re-assigned (e.g. doctor became absent)."""
    appt = await _load_or_fail(s, appointment_id)
    if appt.status not in ("requested", "approved"):
        raise HttpError(409, f"Appointment is already {appt.status}")

    doctors = await doctor_availability_service.for_date(s, appt.specialty, appt.appointment_date)
    doctor = next((d for d in doctors if d["id"] == data.doctor_id), None)
    if not doctor:
        raise HttpError(400, "Doctor does not match the patient's required specialty")
    if not doctor["available"]:
        raise HttpError(409, f"Dr. {doctor['fullName']} is not available on this date ({doctor['reason']})")

    appointment_repository.update(
        appt, doctor_id=doctor["id"], status="approved", note=data.note, handled_by=actor.id, handled_at=utc_now()
    )
    await s.commit()
    return row(appt)


async def reject(s: AsyncSession, actor: User, appointment_id: str, note: str | None) -> dict:
    appt = await _load_or_fail(s, appointment_id)
    if appt.status != "requested":
        raise HttpError(409, f"Appointment is already {appt.status}")
    appointment_repository.update(appt, status="rejected", note=note, handled_by=actor.id, handled_at=utc_now())
    await s.commit()
    return row(appt)


async def cancel(s: AsyncSession, actor: User, appointment_id: str) -> dict:
    """Patients cancel their own; receptionists / super admin cancel any."""
    appt = await _load_or_fail(s, appointment_id)
    if appt.patient_id != actor.id and not await permission_service.can_use_reception(s, actor):
        raise HttpError(403, "You can only cancel your own appointments")
    if appt.status not in ("requested", "approved"):
        raise HttpError(409, f"Appointment is already {appt.status}")
    appointment_repository.update(appt, status="cancelled")
    await s.commit()
    return row(appt)
