from typing import Literal, Optional

from app.schemas.common_schema import IsoDate
from app.schemas.pagination_schema import PaginationQuery


class DoctorPatientsQuery(PaginationQuery):
    """Doctor's list of assigned patients."""

    status: Optional[Literal["approved", "checked"]] = None
    date: Optional[IsoDate] = None


class CheckedVisitsQuery(PaginationQuery):
    """List of checked patients shared with reception and accounts."""

    date: Optional[IsoDate] = None
