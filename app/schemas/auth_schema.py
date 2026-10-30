from typing import Optional

from pydantic import Field, model_validator

from app.schemas.common_schema import CamelModel, Email, IsoDate, Password, TotpCode
from app.schemas.patient_schema import BloodGroup, Gender


class RegisterIn(CamelModel):
    email: Email
    password: Password
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    date_of_birth: Optional[IsoDate] = None
    gender: Optional[Gender] = None
    blood_group: Optional[BloodGroup] = None
    address: Optional[str] = Field(default=None, max_length=500)


class LoginIn(CamelModel):
    email: Email
    password: str = Field(min_length=1)


class MfaCodeIn(CamelModel):
    code: TotpCode


class MfaLoginIn(CamelModel):
    code: Optional[TotpCode] = None
    recovery_code: Optional[str] = Field(default=None, min_length=5, max_length=20)

    @model_validator(mode="after")
    def _exactly_one(self):
        if bool(self.code) == bool(self.recovery_code):
            raise ValueError("Provide exactly one of code or recoveryCode")
        return self


class MfaRevealIn(CamelModel):
    password: str = Field(min_length=1)
    code: TotpCode


class MfaDisableIn(MfaRevealIn):
    pass
