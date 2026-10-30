from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk


class Prescription(Base):
    """A PDF prescription attached by the doctor to an appointment. The file lives in UPLOAD_DIR."""

    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    appointment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("appointments.id", ondelete="cascade"))
    patient_id: Mapped[str] = required_user_fk()
    doctor_id: Mapped[str | None] = user_fk()
    # Original file name shown to users.
    file_name: Mapped[str] = mapped_column(String(255))
    # Generated name on disk.
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
