from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk
from .enums import appointment_status_enum, specialty_enum


class Appointment(Base):
    """A patient's request for treatment on a date; a receptionist assigns a doctor and approves it."""

    __tablename__ = "appointments"
    __table_args__ = (Index("appointments_status_date_idx", "status", "appointment_date"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    patient_id: Mapped[str] = required_user_fk()
    # The patient's requirement, e.g. OPD or cardiologist.
    specialty: Mapped[str] = mapped_column(specialty_enum)
    requested_doctor_id: Mapped[str | None] = user_fk()
    # Doctor assigned by the receptionist.
    doctor_id: Mapped[str | None] = user_fk()
    appointment_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(appointment_status_enum, server_default="requested")
    # Receptionist's note when approving / rejecting.
    note: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[str | None] = user_fk()
    handled_at: Mapped[datetime | None] = mapped_column(Timestamp)
    # Set when the doctor marks the patient as checked (consultation done).
    checked_at: Mapped[datetime | None] = mapped_column(Timestamp)
    # Doctor's consultation fee at the moment the patient was checked: revenue history stays stable.
    checked_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    checked_by: Mapped[str | None] = user_fk()
    created_by: Mapped[str | None] = user_fk()
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
