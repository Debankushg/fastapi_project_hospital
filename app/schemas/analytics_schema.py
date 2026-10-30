from typing import Annotated, Literal, Optional

from pydantic import Field, StringConstraints, model_validator

from app.schemas.common_schema import CamelModel, FieldError, IsoDate, Uuid


class AnalyticsQuery(CamelModel):
    """Date window for a chart. The client sends local dates so "today" matches the user's calendar."""

    from_: IsoDate = Field(alias="from")
    to: IsoDate
    group_by: Literal["day", "month"] = "day"

    @model_validator(mode="after")
    def _range(self):
        if self.to < self.from_:
            raise FieldError("to", "to must not be before from")
        if (self.to - self.from_).days + 1 > 400:
            raise FieldError("to", "Range is limited to 400 days")
        return self


class AttendanceCalendarQuery(CamelModel):
    month: Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    # View another staff member (managers only). Omit for your own calendar.
    user_id: Optional[Uuid] = None
    # The viewer's local date, used to tell "not marked yet" from "future".
    today: Optional[IsoDate] = None
