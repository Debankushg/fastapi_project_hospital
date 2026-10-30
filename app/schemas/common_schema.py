import re
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel


class FieldError(ValueError):
    """Raised from a model-level validator to attach the message to one field (like a zod refine `path`)."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class CamelModel(BaseModel):
    """Snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _iso_date(v):
    if isinstance(v, date):
        return v
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError("Use YYYY-MM-DD")
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise ValueError("Not a valid calendar date") from None


def _email(v: str) -> str:
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
        raise ValueError("Invalid email")
    return v


def _strong_password(v: str) -> str:
    if len(v) < 10:
        raise ValueError("at least 10 characters")
    if not re.search(r"[a-z]", v):
        raise ValueError("needs a lowercase letter")
    if not re.search(r"[A-Z]", v):
        raise ValueError("needs an uppercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("needs a digit")
    if not re.search(r"[^A-Za-z0-9]", v):
        raise ValueError("needs a symbol")
    return v


IsoDate = Annotated[date, BeforeValidator(_iso_date)]
Email = Annotated[str, AfterValidator(_email)]
Password = Annotated[str, StringConstraints(max_length=128), AfterValidator(_strong_password)]
TotpCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]
Uuid = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
]
