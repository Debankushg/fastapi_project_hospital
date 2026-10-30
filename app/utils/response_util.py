import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi.responses import JSONResponse


def _default(o: Any):
    if isinstance(o, datetime):
        if o.tzinfo is None:
            o = o.replace(tzinfo=timezone.utc)
        # JS-style ISO string: 2024-01-31T10:00:00.000Z
        return o.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if isinstance(o, (date, time)):
        return o.isoformat()
    if isinstance(o, (Decimal, UUID)):  # numeric columns are strings, like the Node API
        return str(o)
    raise TypeError(f"Cannot serialise {type(o).__name__}")


class ApiJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, default=_default, ensure_ascii=False, separators=(",", ":")).encode()


def ok(data: Any = None, status: int = 200) -> ApiJSONResponse:
    return ApiJSONResponse(data, status_code=status)
