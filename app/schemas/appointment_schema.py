from typing import Optional

from pydantic import Field

from app.schemas.common_schema import CamelModel, IsoDate, Uuid
from app.schemas.pagination_schema import PaginationQuery
from app.typings.domain_types import AppointmentStatus, Specialty


class CreateAppointmentIn(CamelModel):
    # Required when a receptionist books for a patient; ignored for patients (they book for themselves).
    patient_id: Optional[Uuid] = None
    specialty: Specialty
    preferred_doctor_id: Optional[Uuid] = None
    date: IsoDate
    reason: Optional[str] = Field(default=None, max_length=500)


class AppointmentListQuery(PaginationQuery):
    status: Optional[AppointmentStatus] = None
    date: Optional[IsoDate] = None


class AvailabilityQuery(CamelModel):
    specialty: Specialty
    date: IsoDate


class ApproveAppointmentIn(CamelModel):
    doctor_id: Uuid
    note: Optional[str] = Field(default=None, max_length=500)


class RejectAppointmentIn(CamelModel):
    note: Optional[str] = Field(default=None, max_length=500)
