from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import NOW, UUID_PK, Base, Timestamp, required_user_fk, user_fk
from .enums import payment_status_enum


class Payment(Base):
    """A Stripe Checkout payment for a checked visit. Card details never reach this server."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), **UUID_PK)
    appointment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("appointments.id", ondelete="cascade"))
    patient_id: Mapped[str] = required_user_fk()
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(payment_status_enum, server_default="pending")
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255))
    # Staff member who started the payment.
    created_by: Mapped[str | None] = user_fk()
    paid_at: Mapped[datetime | None] = mapped_column(Timestamp)
    created_at: Mapped[datetime] = mapped_column(Timestamp, **NOW)
