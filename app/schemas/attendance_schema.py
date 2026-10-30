from typing import Optional

from pydantic import Field

from app.schemas.common_schema import CamelModel, IsoDate, Uuid
from app.typings.domain_types import AttendanceStatus


class MarkAttendanceIn(CamelModel):
    user_id: Uuid
    date: IsoDate
    status: AttendanceStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class AttendanceQuery(CamelModel):
    date: IsoDate
