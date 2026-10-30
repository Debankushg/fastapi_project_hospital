from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp
from .enums import role_enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(role_enum, server_default="patient")
    # For admins: the staff role they work as (doctor, receptionist…), shown as "Doctor, Admin".
    # Set automatically on promotion; null for admins created without one.
    base_role: Mapped[str | None] = mapped_column(role_enum)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # AES-256-GCM encrypted TOTP secret (iv:tag:ciphertext, hex).
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text)

    failed_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(Timestamp)

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
