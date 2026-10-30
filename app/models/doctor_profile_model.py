from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import specialty_enum


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="cascade"), primary_key=True)
    specialty: Mapped[str] = mapped_column(specialty_enum)
    license_no: Mapped[str] = mapped_column(String(64), unique=True)
    consultation_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
