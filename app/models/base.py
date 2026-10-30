from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Timestamp = DateTime(timezone=True)

# Shared column definitions
UUID_PK = dict(primary_key=True, server_default=text("gen_random_uuid()"))
NOW = dict(server_default=func.now())


class Base(DeclarativeBase):
    pass


def user_fk(*, cascade: bool = False) -> Mapped:
    """Nullable foreign key to users.id (set null on delete, or cascade)."""
    return mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="cascade" if cascade else "set null"))


def required_user_fk() -> Mapped:
    """Required foreign key to users.id; the row goes away with the user."""
    return mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="cascade"))
