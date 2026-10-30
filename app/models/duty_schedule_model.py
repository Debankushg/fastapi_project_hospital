from datetime import datetime, time

from sqlalchemy import ARRAY, ForeignKey, Integer, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, Base, Timestamp, user_fk


class DutySchedule(Base):
    """One weekly duty schedule per staff member."""

    __tablename__ = "duty_schedules"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="cascade"), primary_key=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    # 0 = Sunday … 6 = Saturday
    work_days: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    updated_by: Mapped[str | None] = user_fk()
    updated_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
