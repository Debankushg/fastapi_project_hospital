import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.utils.http_error_util import HttpError
from app.utils.response_util import ApiJSONResponse

log = logging.getLogger("hospital")


def _body(message: str, details: Any = None) -> dict:
    return {"error": message} if details is None else {"error": message, "details": details}


def _internal(e: Exception) -> str:
    return "Internal server error" if settings.NODE_ENV == "production" else str(e)


def _field_errors(exc: RequestValidationError) -> dict[str, list[str]]:
    """Same shape as zod's flatten().fieldErrors: {field: [messages]}."""
    out: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = [p for p in err["loc"] if p not in ("body", "query", "path")]
        cause = (err.get("ctx") or {}).get("error")
        if hasattr(cause, "field"):  # schemas.common_schema.FieldError: message tied to one field
            key = cause.field
        else:
            key = str(loc[-1]) if loc else "_errors"
        out.setdefault(key, []).append(err["msg"].removeprefix("Value error, "))
    return out


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HttpError)
    async def _http_error(_: Request, e: HttpError):
        return ApiJSONResponse(_body(e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        return ApiJSONResponse(_body("Validation failed", _field_errors(e)), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _not_found_and_friends(_: Request, e: StarletteHTTPException):
        message = "Not found" if e.status_code == 404 else str(e.detail)
        return ApiJSONResponse({"error": message}, status_code=e.status_code)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, e: IntegrityError):
        if getattr(e.orig, "sqlstate", None) == "23505":  # Postgres unique violation
            return ApiJSONResponse({"error": "Resource already exists"}, status_code=409)
        log.exception("integrity error")
        return ApiJSONResponse({"error": _internal(e)}, status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, e: Exception):
        log.exception("unhandled error")
        return ApiJSONResponse({"error": _internal(e)}, status_code=500)
