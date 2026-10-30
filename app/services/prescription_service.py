from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import appointment_repository, prescription_repository
from app.services import permission_service
from app.utils.file_storage_util import prescription_file_path
from app.utils.http_error_util import HttpError


async def get_file(s: AsyncSession, actor: User, prescription_id: str) -> tuple[str, str]:
    """Who may open a prescription file: the patient it belongs to, doctors treating that patient,
    reception staff (to hand it to the patient) and the super admin. Accounts only sees that one exists.
    Returns (path on disk, display name)."""
    rx = await prescription_repository.find_by_id(s, prescription_id)
    if not rx:
        raise HttpError(404, "Prescription not found")

    allowed = (
        rx.patient_id == actor.id
        or rx.doctor_id == actor.id
        or (permission_service.is_doctor(actor) and await appointment_repository.doctor_treats_patient(s, actor.id, rx.patient_id))
        or await permission_service.can_use_reception(s, actor)
    )
    if not allowed:
        raise HttpError(403, "You do not have access to this prescription")
    return str(prescription_file_path(rx.stored_name)), rx.file_name
