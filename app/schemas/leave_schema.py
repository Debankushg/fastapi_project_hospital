from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.common_schema import CamelModel, FieldError, IsoDate, Uuid
from app.typings.domain_types import LeaveStatus, LeaveType

MAX_LEAVE_DAYS = 90


class _LeaveFields(CamelModel):
    leave_type: LeaveType
    start_date: IsoDate
    end_date: IsoDate
    reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _range(self):
        if self.end_date < self.start_date:
            raise FieldError("endDate", "End date must not be before start date")
        if (self.end_date - self.start_date).days + 1 > MAX_LEAVE_DAYS:
            raise FieldError("endDate", f"A leave can span at most {MAX_LEAVE_DAYS} days")
        return self


class CreateLeaveIn(_LeaveFields):
    """Admin records leave for a staff member (approved immediately)."""

    user_id: Uuid


class RequestLeaveIn(_LeaveFields):
    """Staff member requests leave for themselves (starts as pending)."""


class ReviewLeaveIn(CamelModel):
    status: Literal["approved", "rejected"]
    note: Optional[str] = Field(default=None, max_length=500)


class LeaveQuery(CamelModel):
    user_id: Optional[Uuid] = None
    status: Optional[LeaveStatus] = None
    from_: Optional[IsoDate] = Field(default=None, alias="from")
    to: Optional[IsoDate] = None
