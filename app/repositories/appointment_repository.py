from datetime import date
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Appointment, DoctorProfile, Payment, Prescription, User
from app.utils.date_util import utc_now
from app.utils.mapper_util import camelize
from app.utils.pagination_util import like_pattern

_requested_doctor = aliased(User, name="requested_doctor")
_assigned_doctor = aliased(User, name="assigned_doctor")

_ORDER = {
    "created_desc": lambda: [Appointment.created_at.desc(), Appointment.id.desc()],
    "date_asc": lambda: [Appointment.appointment_date.asc(), Appointment.created_at.asc(), Appointment.id.asc()],
    "date_desc": lambda: [Appointment.appointment_date.desc(), Appointment.created_at.desc(), Appointment.id.desc()],
    "checked_desc": lambda: [Appointment.checked_at.desc(), Appointment.id.desc()],
}


def create(s: AsyncSession, **values) -> Appointment:
    appt = Appointment(**values)
    s.add(appt)
    return appt


async def find_by_id(s: AsyncSession, appointment_id: str) -> Appointment | None:
    return await s.get(Appointment, appointment_id)


def update(appt: Appointment, **values) -> Appointment:
    """Applies the changes to the loaded appointment (written on the next flush/commit)."""
    for k, v in values.items():
        setattr(appt, k, v)
    appt.updated_at = utc_now()
    return appt


def _paid_exists():
    return exists().where(Payment.appointment_id == Appointment.id, Payment.status == "paid")


async def list_appointments(
    s: AsyncSession,
    *,
    limit: int,
    offset: int,
    patient_id: str | None = None,
    doctor_id: str | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    sort: str = "created_desc",
    day: date | None = None,
    search: str | None = None,
    paid: bool | None = None,  # checked visits only: has a paid Stripe payment (or not)
) -> tuple[list[dict[str, Any]], int]:
    """Appointments joined with the patient and doctors' names, plus the total for pagination."""
    cond: list[Any] = []
    if patient_id:
        cond.append(Appointment.patient_id == patient_id)
    if doctor_id:
        cond.append(Appointment.doctor_id == doctor_id)
    if status:
        cond.append(Appointment.status == status)
    if statuses:
        cond.append(Appointment.status.in_(statuses))
    if day:
        cond.append(Appointment.appointment_date == day)
    if search:
        p = like_pattern(search)
        cond.append(or_(User.full_name.ilike(p, escape="\\"), User.email.ilike(p, escape="\\")))
    if paid is not None:
        cond.append(_paid_exists() if paid else ~_paid_exists())

    prescription_count = (
        select(func.count()).select_from(Prescription).where(Prescription.appointment_id == Appointment.id).scalar_subquery()
    )
    q = (
        select(
            Appointment.id,
            Appointment.specialty,
            Appointment.appointment_date.label("date"),
            Appointment.reason,
            Appointment.status,
            Appointment.note,
            Appointment.created_at,
            Appointment.handled_at,
            Appointment.checked_at,
            prescription_count.label("prescription_count"),
            func.coalesce(Appointment.checked_fee, DoctorProfile.consultation_fee).label("consultation_fee"),
            Appointment.patient_id,
            User.full_name.label("patient_name"),
            User.email.label("patient_email"),
            User.phone.label("patient_phone"),
            Appointment.requested_doctor_id,
            _requested_doctor.full_name.label("requested_doctor_name"),
            Appointment.doctor_id,
            _assigned_doctor.full_name.label("doctor_name"),
        )
        .select_from(Appointment)
        .join(User, User.id == Appointment.patient_id)
        .outerjoin(_requested_doctor, _requested_doctor.id == Appointment.requested_doctor_id)
        .outerjoin(_assigned_doctor, _assigned_doctor.id == Appointment.doctor_id)
        .outerjoin(DoctorProfile, DoctorProfile.user_id == Appointment.doctor_id)
        .where(and_(*cond))
        .order_by(*_ORDER[sort]())
        .limit(limit)
        .offset(offset)
    )
    rows = [camelize(dict(r._mapping)) for r in (await s.execute(q)).all()]
    total = await s.scalar(
        select(func.count()).select_from(Appointment).join(User, User.id == Appointment.patient_id).where(and_(*cond))
    )
    return rows, total or 0


async def doctor_treats_patient(s: AsyncSession, doctor_id: str, patient_id: str) -> bool:
    """True if the doctor has an approved/checked appointment with this patient (a care relationship)."""
    q = (
        select(Appointment.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.patient_id == patient_id,
            Appointment.status.in_(["approved", "checked"]),
        )
        .limit(1)
    )
    return (await s.scalar(q)) is not None


async def count_approved_by_doctors(s: AsyncSession, doctor_ids: list[str], day: date) -> dict[str, int]:
    """Number of approved/checked appointments per doctor on a date (workload hint for the receptionist)."""
    if not doctor_ids:
        return {}
    q = (
        select(Appointment.doctor_id, func.count())
        .where(
            Appointment.doctor_id.in_(doctor_ids),
            Appointment.appointment_date == day,
            Appointment.status.in_(["approved", "checked"]),
        )
        .group_by(Appointment.doctor_id)
    )
    return {doctor_id: n for doctor_id, n in (await s.execute(q)).all()}
