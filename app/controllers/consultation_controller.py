import os
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.consultation_schema import CheckedVisitsQuery, DoctorPatientsQuery
from app.services import consultation_service, prescription_service
from app.utils.http_error_util import HttpError
from app.utils.response_util import ok

MAX_BYTES = consultation_service.MAX_PRESCRIPTION_BYTES


async def _read_pdf_body(request: Request) -> bytes:
    """The PDF is the raw request body (Content-Type: application/pdf, max 5 MB); anything else reads as empty."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
        return b""
    if int(request.headers.get("content-length") or 0) > MAX_BYTES:
        raise HttpError(413, "File too large (max 5 MB)")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BYTES:
            raise HttpError(413, "File too large (max 5 MB)")
    return bytes(body)


async def list_patients(s: AsyncSession, actor: User, q: DoctorPatientsQuery):
    return ok(await consultation_service.list_patients(s, actor, q))


async def detail(s: AsyncSession, actor: User, appointment_id: str):
    return ok(await consultation_service.detail(s, actor, appointment_id))


async def add_prescription(s: AsyncSession, actor: User, appointment_id: str, request: Request, file_name: str | None):
    pdf = await _read_pdf_body(request)
    return ok({"prescription": await consultation_service.add_prescription(s, actor, appointment_id, pdf, file_name)}, 201)


async def check(s: AsyncSession, actor: User, appointment_id: str):
    await consultation_service.check(s, actor, appointment_id)
    return ok({"checked": True})


async def list_checked(s: AsyncSession, actor: User, q: CheckedVisitsQuery):
    return ok(await consultation_service.list_checked(s, actor, q))


async def remove_prescription(s: AsyncSession, actor: User, prescription_id: str):
    await consultation_service.remove_prescription(s, actor, prescription_id)
    return Response(status_code=204)


async def prescription_file(s: AsyncSession, actor: User, prescription_id: str):
    """Streams the PDF inline. Auth is a bearer header, so the frontend fetches it as a blob."""
    path, file_name = await prescription_service.get_file(s, actor, prescription_id)
    if not os.path.isfile(path):
        raise HttpError(404, "Prescription file not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(file_name, safe='')}",
            "Cache-Control": "private, no-store",
        },
    )
