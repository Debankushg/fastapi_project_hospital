from datetime import datetime

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk
from .enums import admin_area_enum


class AdminAssignment(Base):
    __tablename__ = "admin_assignments"
    __table_args__ = (
        UniqueConstraint("admin_id", "area"),
        # One admin per department: an area can belong to only one admin at a time.
        UniqueConstraint("area", name="admin_assignments_area_unique"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    admin_id: Mapped[str] = required_user_fk()
    area: Mapped[str] = mapped_column(admin_area_enum)
    notes: Mapped[str | None] = mapped_column(Text)
    assigned_by: Mapped[str | None] = user_fk()
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
