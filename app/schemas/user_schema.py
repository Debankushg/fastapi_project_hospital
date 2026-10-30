from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.common_schema import CamelModel, Email, FieldError, Password
from app.typings.domain_types import Role, Specialty

# Roles that admins/super admins may create through POST /users (admins have their own endpoint).
CREATABLE_ROLES = ["doctor", "receptionist", "pathologist", "accounts", "patient"]


class CreateUserIn(CamelModel):
    email: Email
    password: Password
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    role: Literal[tuple(CREATABLE_ROLES)]  # type: ignore[valid-type]
    specialty: Optional[Specialty] = None
    license_no: Optional[str] = Field(default=None, min_length=3, max_length=64)
    consultation_fee: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _doctor_fields(self):
        if self.role == "doctor" and not (self.specialty and self.license_no):
            raise FieldError("specialty", "specialty and licenseNo are required for doctors")
        return self


class ListUsersQuery(CamelModel):
    role: Optional[Role] = None


class SetActiveIn(CamelModel):
    is_active: bool


class DoctorQuery(CamelModel):
    specialty: Optional[Specialty] = None
