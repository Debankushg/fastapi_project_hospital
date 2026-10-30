import re

from app.typings.pagination_types import Paginated


def offset_of(page: int, page_size: int) -> int:
    return (page - 1) * page_size


def to_page(items: list, total: int, page: int, page_size: int) -> Paginated:
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": max(1, -(-total // page_size)),
    }


def like_pattern(search: str) -> str:
    """Escapes % and _ so user input is matched literally by ILIKE (use escape="\\\\")."""
    return "%" + re.sub(r"([\\%_])", r"\\\1", search) + "%"
