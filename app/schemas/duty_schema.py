import re
from datetime import time
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from app.schemas.common_schema import CamelModel, FieldError


def _hhmm(v):
    if not isinstance(v, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
        raise ValueError("Use HH:MM (24h)")
    return time.fromisoformat(v)


HHMM = Annotated[time, BeforeValidator(_hhmm)]


class DutyScheduleIn(CamelModel):
    start_time: HHMM
    end_time: HHMM
    # 0 = Sunday … 6 = Saturday
    work_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        if len(set(self.work_days)) != len(self.work_days):
            raise FieldError("workDays", "Duplicate days")
        if self.start_time == self.end_time:
            raise FieldError("endTime", "Start and end time must differ")
        return self
