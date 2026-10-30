from typing import Literal

from pydantic import Field

from app.schemas.common_schema import CamelModel, Uuid
from app.schemas.pagination_schema import PaginationQuery


class StartCheckoutIn(CamelModel):
    appointment_id: Uuid


class SyncPaymentIn(CamelModel):
    session_id: str = Field(min_length=5, max_length=255)


class ReceivablesQuery(PaginationQuery):
    """Checked visits with their payment state."""

    status: Literal["all", "unpaid", "paid"] = "unpaid"
