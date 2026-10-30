from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import UUID_PK, Base, Timestamp, required_user_fk


class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    user_id: Mapped[str] = required_user_fk()
    code_hash: Mapped[str] = mapped_column(Text)
    used_at: Mapped[datetime | None] = mapped_column(Timestamp)
