from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.common_schema import CamelModel, Email, FieldError, Password
from app.typings.domain_types import AdminArea

# Staff roles an admin can "work as"; they decide which department lists the admin.
BASE_ROLES = ["doctor", "receptionist", "pathologist", "accounts"]
BaseRole = Literal[tuple(BASE_ROLES)]  # type: ignore[valid-type]


class AssignmentItem(CamelModel):
    area: AdminArea
    notes: Optional[str] = Field(default=None, max_length=500)


class AdminAssignmentsIn(CamelModel):
    assignments: list[AssignmentItem] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_areas(self):
        if len({a.area for a in self.assignments}) != len(self.assignments):
            raise FieldError("assignments", "Duplicate areas")
        return self


class UpdateAdminWorkIn(AdminAssignmentsIn):
    """Promote / change work. `baseRole` (the admin's profession) is optional here: promotion fills it from the
    user's previous role and omitting it on update leaves it unchanged. It can never be cleared."""

    base_role: Optional[BaseRole] = None


class CreateAdminIn(AdminAssignmentsIn):
    # Required: the profession decides which department lists the admin ("Doctor, Admin").
    base_role: BaseRole
    email: Email
    password: Password
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)


class DemoteAdminIn(CamelModel):
    role: Literal["receptionist", "pathologist", "accounts", "patient"]
