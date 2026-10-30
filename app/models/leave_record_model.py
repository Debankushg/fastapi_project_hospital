from datetime import date, datetime

from sqlalchemy import Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk
from .enums import leave_status_enum, leave_type_enum


class LeaveRecord(Base):
    __tablename__ = "leave_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    user_id: Mapped[str] = required_user_fk()
    leave_type: Mapped[str] = mapped_column(leave_type_enum)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    # Admin-recorded leave is approved immediately; staff requests start as pending.
    status: Mapped[str] = mapped_column(leave_status_enum, server_default="approved")
    reviewed_by: Mapped[str | None] = user_fk()
    reviewed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    review_note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[str | None] = user_fk()
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
