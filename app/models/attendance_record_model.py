import datetime as dt

from sqlalchemy import Date, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk
from .enums import attendance_status_enum


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    user_id: Mapped[str] = required_user_fk()
    date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(attendance_status_enum)
    notes: Mapped[str | None] = mapped_column(Text)
    marked_by: Mapped[str | None] = user_fk()
    created_at: Mapped[dt.datetime] = mapped_column(Timestamp, **NOW)
    updated_at: Mapped[dt.datetime] = mapped_column(Timestamp, **NOW)
