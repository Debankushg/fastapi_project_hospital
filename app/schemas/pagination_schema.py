from typing import Annotated, Optional

from pydantic import Field, StringConstraints

from .common_schema import CamelModel


class PaginationQuery(CamelModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: Annotated[Optional[str], StringConstraints(strip_whitespace=True, max_length=100)] = None
