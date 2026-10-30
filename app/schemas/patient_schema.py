from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.common_schema import CamelModel, FieldError, IsoDate
from app.schemas.pagination_schema import PaginationQuery

Gender = Literal["male", "female", "other"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class PatientListQuery(PaginationQuery):
    sort_by: Literal["name", "joined"] = "name"
    order: Literal["asc", "desc"] = "asc"


class UpdatePatientIn(CamelModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    date_of_birth: Optional[IsoDate] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise FieldError("fullName", "fullName cannot be null")
        return self
