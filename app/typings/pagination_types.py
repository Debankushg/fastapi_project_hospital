from typing import Any, TypedDict


class Paginated(TypedDict):
    items: list[Any]
    page: int
    pageSize: int
    total: int
    totalPages: int
